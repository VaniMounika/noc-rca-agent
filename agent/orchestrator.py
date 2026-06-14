"""
NOC Incident RCA Agent - Orchestrator
=======================================
Five-step reasoning chain:

  1. Classify     - extract structured fields from the raw alert
  2. Correlate    - Foundry IQ agentic retrieval (Azure AI Search + runbooks)
  3. RCA Reason   - GPT-4o (Azure AI Foundry) chain-of-thought root cause analysis
  4. Recommend    - Fabric IQ semantic ontology -> assignee, runbook, SLA risk
  5. Compliance   - MAS Compliance Agent -> drafts regulatory notification if
                     the transaction impact exceeds the MAS TRM threshold

Each tool returns a typed dataclass. The orchestrator chains them sequentially,
feeding each tool's output into the next. A human approval gate (in the UI)
is required before any ticket assignment - the agent recommends, a human decides.

Run directly for a CLI smoke test: `python -m agent.orchestrator`
"""

import os
import re
import json
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

from agent.fabric_iq_mock import get_service_context, check_mas_threshold, FABRIC_IQ_ONTOLOGY
from agent.foundry_iq_client import (
    retrieve_similar_incidents,
    generate_rca_with_llm,
    foundry_iq_configured,
    azure_openai_configured,
)

load_dotenv()


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class ClassifyResult:
    category: str
    severity: str
    service: str
    region: str
    environment: str
    txn_count: int
    confidence: float


@dataclass
class SimilarIncident:
    incident_id: str
    title: str
    root_cause: str
    resolution: str
    resolution_time_min: int
    similarity_note: str


@dataclass
class CorrelateResult:
    similar_incidents: list
    runbook_id: str
    runbook_excerpt: str
    source: str  # "Foundry IQ (Azure AI Search)" | "Local knowledge base (Foundry IQ fallback)"


@dataclass
class RCAResult:
    probable_root_cause: str
    confidence: str          # HIGH / MEDIUM / LOW
    evidence_citations: list
    contributing_factors: list
    reasoning_source: str     # "GPT-4o (Azure AI Foundry)" | "Heuristic (offline mode)"


@dataclass
class RecommendResult:
    assignee: str
    team: str
    runbook_id: str
    escalation: str
    business_criticality: str
    remediation_steps: list
    sla_risk: str            # LOW / MEDIUM / HIGH / CRITICAL
    sla_target_minutes: int


@dataclass
class ComplianceResult:
    mas_flag: bool
    notification_required: bool
    notification_draft: str


@dataclass
class RCAReport:
    incident_title: str
    raw_alert: str
    classify: ClassifyResult
    correlate: CorrelateResult
    rca: RCAResult
    recommend: RecommendResult
    compliance: ComplianceResult


# ── Tool 1 - Classify ────────────────────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "DB Connectivity":   ["database", "db", "connection pool", "postgres", "sql", "replica", "timeout", "db-"],
    "Payment Gateway":   ["payment", "gateway", "visa", "mastercard", "transaction", "settlement", "txn"],
    "Auth Service":      ["auth", "login", "oauth", "token", "mfa", "session", "identity", "unauthori"],
    "FX Feed":           ["fx", "forex", "rate feed", "reuters", "bloomberg", "currency", "exchange rate"],
    "SWIFT Queue":       ["swift", "queue", "mq", "message", "broker", "bic", "correspondent"],
    "Batch Job":         ["batch", "eod", "reconciliation", "job", "scheduler", "settlement batch"],
    "Network":           ["network", "bgp", "firewall", "vpc", "route", "load balancer", "packet loss"],
    "Application Error": ["api", "500", "null pointer", "exception", "app", "mobile", "teller", "banking"],
}

SEVERITY_KEYWORDS = {
    "P1": ["p1", "critical", "down", "outage", "all users", "production down", "complete failure"],
    "P2": ["p2", "degraded", "slow", "partial", "intermittent", "some users", "high impact"],
    "P3": ["p3", "minor", "low impact", "workaround", "non-critical"],
    "P4": ["p4", "informational", "cosmetic", "no impact"],
}

KNOWN_SERVICES = [svc for entry in FABRIC_IQ_ONTOLOGY.values() for svc in entry["services"]]


def classify_incident(alert_text: str) -> ClassifyResult:
    """Tool 1: Classify the raw alert into structured fields."""
    text = alert_text.lower()

    category_scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in CATEGORY_KEYWORDS.items()}
    category = max(category_scores, key=category_scores.get)
    confidence = min(category_scores[category] / 3.0, 1.0)

    severity = "P2"
    for sev, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            severity = sev
            break

    service = next((svc for svc in KNOWN_SERVICES if svc in text), None)
    if service is None:
        service = FABRIC_IQ_ONTOLOGY.get(category, {}).get("services", ["unknown-service"])[0]

    region = "Hong Kong" if ("hong kong" in text or " hk" in text or "-hk" in text) else "Singapore"
    environment = "Staging" if any(k in text for k in ["staging", "uat", "dev"]) else "Production"

    txn_count = 0
    match = re.search(r"(\d[\d,]*)\s*(txn|transaction|payment)", text)
    if match:
        txn_count = int(match.group(1).replace(",", ""))

    return ClassifyResult(
        category=category, severity=severity, service=service, region=region,
        environment=environment, txn_count=txn_count, confidence=round(confidence, 2),
    )


# ── Tool 2 - Correlate (Foundry IQ) ─────────────────────────────────────────

def correlate_incidents(classify_result: ClassifyResult, top_k: int = 3) -> CorrelateResult:
    """Tool 2: Foundry IQ agentic retrieval - similar incidents + runbook."""
    docs, runbook, source = retrieve_similar_incidents(
        category=classify_result.category,
        service=classify_result.service,
        region=classify_result.region,
        severity=classify_result.severity,
        top_k=top_k,
    )

    similar = []
    for d in docs:
        note = d.title.split("(")[-1].rstrip(")") if "(" in d.title else "same category"
        similar.append(SimilarIncident(
            incident_id=d.doc_id,
            title=d.title.split(" (")[0],
            root_cause=d.root_cause,
            resolution=d.resolution,
            resolution_time_min=d.resolution_time_min,
            similarity_note=note,
        ))

    runbook_id = runbook.doc_id if runbook else "RB-GENERIC-001"
    runbook_excerpt = runbook.content[:600] if runbook else ""

    return CorrelateResult(
        similar_incidents=similar,
        runbook_id=runbook_id,
        runbook_excerpt=runbook_excerpt,
        source=source,
    )


# ── Tool 3 - RCA Reason (GPT-4o via Azure AI Foundry) ───────────────────────

def reason_rca(alert_text: str, classify_result: ClassifyResult, correlate_result: CorrelateResult) -> RCAResult:
    """Tool 3: GPT-4o chain-of-thought RCA, grounded in Foundry IQ retrieval."""
    from agent.foundry_iq_client import RetrievedDoc

    similar_docs = [
        RetrievedDoc(
            doc_id=s.incident_id, doc_type="incident", title=s.title, content="",
            root_cause=s.root_cause, resolution=s.resolution,
            resolution_time_min=s.resolution_time_min, source="local",
        )
        for s in correlate_result.similar_incidents
    ]
    runbook_doc = None
    if correlate_result.runbook_excerpt:
        runbook_doc = RetrievedDoc(
            doc_id=correlate_result.runbook_id, doc_type="runbook",
            title=f"Runbook {correlate_result.runbook_id}",
            content=correlate_result.runbook_excerpt, source="local",
        )

    probable_rc, confidence, factors, reasoning_source = generate_rca_with_llm(
        alert_text=alert_text,
        category=classify_result.category,
        service=classify_result.service,
        region=classify_result.region,
        severity=classify_result.severity,
        txn_count=classify_result.txn_count,
        similar_incidents=similar_docs,
        runbook=runbook_doc,
    )

    if classify_result.environment == "Production" and "Environment:" not in " ".join(factors):
        factors.append("Environment: Production - elevated risk of customer and regulatory impact")

    citations = [s.incident_id for s in correlate_result.similar_incidents]

    return RCAResult(
        probable_root_cause=probable_rc,
        confidence=confidence,
        evidence_citations=citations,
        contributing_factors=factors,
        reasoning_source=reasoning_source,
    )


# ── Tool 4 - Recommend (Fabric IQ semantic ontology) ────────────────────────

def recommend_action(classify_result: ClassifyResult, correlate_result: CorrelateResult) -> RecommendResult:
    """Tool 4: Fabric IQ ontology query -> assignee, team, escalation, SLA."""
    ctx = get_service_context(classify_result.category, classify_result.severity)

    if correlate_result.similar_incidents:
        top_res = correlate_result.similar_incidents[0].resolution
        steps = [s.strip() for s in top_res.split(".") if s.strip()]
    else:
        steps = ["Escalate to on-call engineer immediately.", f"Refer to runbook {ctx.runbook_id}."]

    sla_risk_map = {"P1": "CRITICAL", "P2": "HIGH", "P3": "MEDIUM", "P4": "LOW"}
    sla_risk = sla_risk_map.get(classify_result.severity, "MEDIUM")

    return RecommendResult(
        assignee=ctx.assignee,
        team=ctx.team,
        runbook_id=ctx.runbook_id,
        escalation=ctx.escalation,
        business_criticality=ctx.business_criticality,
        remediation_steps=steps,
        sla_risk=sla_risk,
        sla_target_minutes=ctx.sla_target_minutes,
    )


# ── Tool 5 - MAS Compliance Agent ───────────────────────────────────────────

def compliance_check(classify_result: ClassifyResult, rca_result: RCAResult,
                      recommend_result: RecommendResult, incident_title: str) -> ComplianceResult:
    """
    Tool 5: MAS Compliance Agent.

    If the transaction impact exceeds the MAS Technology Risk Management (TRM)
    reporting threshold (Fabric IQ business rule), this tool drafts a structured
    compliance notification ready for the compliance team to review and submit.
    This is a genuine 5th reasoning step, not just a flag - it produces a
    bank-ready document.
    """
    mas_flag, mas_note = check_mas_threshold(classify_result.txn_count)

    if not mas_flag:
        return ComplianceResult(mas_flag=False, notification_required=False, notification_draft="")

    draft = f"""MAS TECHNOLOGY RISK MANAGEMENT — INCIDENT NOTIFICATION (DRAFT)
================================================================
Regulation reference : MAS Notice 655 - Technology Risk Management
Incident             : {incident_title}
Severity             : {classify_result.severity}
Affected service     : {classify_result.service} ({classify_result.region}, {classify_result.environment})
Transactions affected: {classify_result.txn_count:,}

Root cause (preliminary):
{rca_result.probable_root_cause}

Confidence level     : {rca_result.confidence}
Evidence references  : {', '.join(rca_result.evidence_citations) or 'N/A'}

Remediation owner    : {recommend_result.assignee} ({recommend_result.team})
Escalation contact   : {recommend_result.escalation}

Notification basis   : {mas_note}

--- DRAFT ONLY ---
This notification has been auto-drafted by the NOC Incident RCA Agent based on
preliminary classification and root cause analysis. It must be reviewed and
approved by the Compliance team before submission to MAS, in line with the
60-minute notification window under MAS Notice 655.
"""

    return ComplianceResult(mas_flag=True, notification_required=True, notification_draft=draft)


# ── Main orchestrator ───────────────────────────────────────────────────────

def run_agent(alert_text: str, incident_title: str = "") -> RCAReport:
    """Full reasoning chain: Classify -> Correlate -> RCA -> Recommend -> Compliance."""
    title = incident_title or alert_text[:80]

    classify_result = classify_incident(alert_text)
    correlate_result = correlate_incidents(classify_result)
    rca_result = reason_rca(alert_text, classify_result, correlate_result)
    recommend_result = recommend_action(classify_result, correlate_result)
    compliance_result = compliance_check(classify_result, rca_result, recommend_result, title)

    return RCAReport(
        incident_title=title,
        raw_alert=alert_text,
        classify=classify_result,
        correlate=correlate_result,
        rca=rca_result,
        recommend=recommend_result,
        compliance=compliance_result,
    )


def integration_status() -> dict:
    """Returns which real Azure integrations are active vs. running in fallback mode."""
    return {
        "foundry_iq": "Connected (Azure AI Search)" if foundry_iq_configured() else "Fallback (local knowledge base)",
        "gpt4o": "Connected (Azure AI Foundry)" if azure_openai_configured() else "Fallback (heuristic reasoning)",
    }


if __name__ == "__main__":
    print("Integration status:", json.dumps(integration_status(), indent=2))
    print()

    alert = (
        "P1 CRITICAL - payment-gateway-sg is returning 503 for all settlement requests. "
        "847 txn affected. Singapore Production. Detected at 03:42 SGT. "
        "Upstream Visa adapter health check failing continuously."
    )
    report = run_agent(alert, "Payment gateway timeout - prod SG")
    print(json.dumps(asdict(report), indent=2))

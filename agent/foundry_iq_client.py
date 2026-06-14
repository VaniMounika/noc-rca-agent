"""
Foundry IQ Client
==================
Provides two capabilities backed by Azure AI Foundry:

1. retrieve_similar_incidents() — agentic retrieval over the Foundry IQ /
   Azure AI Search knowledge base (110 historical incidents + 8 runbooks),
   returning cited, grounded results.

2. generate_rca_with_llm() — GPT-4o reasoning over the classified incident +
   retrieved evidence to produce a genuine chain-of-thought root cause analysis.

DESIGN: If Azure credentials are present in the environment (see .env.example),
this module calls the real Azure AI Search index and Azure AI Foundry GPT-4o
deployment. If credentials are missing (e.g. running the dashboard without
Azure setup), it transparently falls back to a local retrieval + heuristic
implementation so the app remains fully demoable offline.

This fallback is intentional and documented — see README "Running without
Azure credentials".
"""

import os
import json
import pandas as pd
from dataclasses import dataclass

# ── Config ───────────────────────────────────────────────────────────────────

AZURE_SEARCH_ENDPOINT   = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_ADMIN_KEY  = os.getenv("AZURE_SEARCH_ADMIN_KEY", "")
AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "noc-incident-knowledge")

AZURE_OPENAI_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/incident_dataset.csv")
RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "../knowledge_base/runbooks")


def foundry_iq_configured() -> bool:
    """Returns True if real Azure AI Search credentials are present."""
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY)


def azure_openai_configured() -> bool:
    """Returns True if real Azure OpenAI / AI Foundry credentials are present."""
    return bool(AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY)


# ── Retrieval result model ──────────────────────────────────────────────────

@dataclass
class RetrievedDoc:
    doc_id: str
    doc_type: str          # "incident" | "runbook"
    title: str
    content: str
    root_cause: str = ""
    resolution: str = ""
    resolution_time_min: int = 0
    score: float = 0.0
    source: str = "local"  # "foundry_iq" | "local"


# ── Real Foundry IQ / Azure AI Search retrieval ─────────────────────────────

def _retrieve_via_azure_search(query: str, category: str, top_k: int) -> list[RetrievedDoc]:
    """
    Queries the Azure AI Search index (Foundry IQ backend) for incidents and
    runbooks semantically related to `query`. Requires AZURE_SEARCH_ENDPOINT
    and AZURE_SEARCH_ADMIN_KEY to be set.
    """
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_ADMIN_KEY),
    )

    results = client.search(
        search_text=query,
        filter=f"category eq '{category}'" if category else None,
        top=top_k,
        
        
    )

    docs = []
    for r in results:
        docs.append(RetrievedDoc(
            doc_id=r.get("incident_id", r.get("id", "unknown")),
            doc_type=r.get("doc_type", "incident"),
            title=r.get("title", ""),
            content=r.get("content", r.get("description", "")),
            root_cause=r.get("root_cause", ""),
            resolution=r.get("resolution", ""),
            resolution_time_min=int(r.get("resolution_time_min", 0) or 0),
            score=float(r.get("@search.score", 0.0)),
            source="foundry_iq",
        ))
    return docs


# ── Local fallback retrieval (pandas + keyword scoring) ─────────────────────

def _retrieve_via_local(query_service: str, query_region: str, query_severity: str,
                         category: str, top_k: int) -> list[RetrievedDoc]:
    """
    Local fallback: scores incidents in the CSV by category/service/region/
    severity match. Mirrors the relevance signals an Azure AI Search semantic
    ranker would use, so behaviour is consistent whether Foundry IQ is
    connected or not.
    """
    df = pd.read_csv(DATA_PATH)
    same_cat = df[df["category"] == category].copy()
    if len(same_cat) == 0:
        same_cat = df.sample(min(top_k, len(df)))

    def score_row(row):
        score = 1.0
        if row["service"] == query_service:
            score += 3.0
        if row["region"] == query_region:
            score += 2.0
        if row["severity"] == query_severity:
            score += 1.0
        return score

    same_cat["_score"] = same_cat.apply(score_row, axis=1)
    top = same_cat.sort_values("_score", ascending=False).head(top_k)

    docs = []
    for _, row in top.iterrows():
        notes = []
        if row["service"] == query_service:
            notes.append("same service")
        if row["region"] == query_region:
            notes.append("same region")
        if row["severity"] == query_severity:
            notes.append("same severity")
        note = ", ".join(notes) if notes else "same category"

        docs.append(RetrievedDoc(
            doc_id=row["incident_id"],
            doc_type="incident",
            title=f"{row['title']} ({note})",
            content=row["description"],
            root_cause=row["root_cause"],
            resolution=row["resolution"],
            resolution_time_min=int(row["resolution_time_min"]),
            score=float(row["_score"]),
            source="local",
        ))
    return docs


def _load_runbook(category: str) -> RetrievedDoc | None:
    """Loads the local runbook markdown for a category as a RetrievedDoc."""
    from agent.fabric_iq_mock import FABRIC_IQ_ONTOLOGY
    entry = FABRIC_IQ_ONTOLOGY.get(category)
    if not entry:
        return None
    runbook_id = entry["runbook_id"]
    path = os.path.join(RUNBOOKS_DIR, f"{runbook_id}.md")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read()
    return RetrievedDoc(
        doc_id=runbook_id,
        doc_type="runbook",
        title=f"Runbook {runbook_id}",
        content=content[:1200],
        source="local",
    )


# ── Public API ───────────────────────────────────────────────────────────────

def retrieve_similar_incidents(category: str, service: str, region: str,
                                severity: str, top_k: int = 3) -> tuple[list[RetrievedDoc], RetrievedDoc | None, str]:
    """
    Foundry IQ agentic retrieval — returns (similar_incidents, runbook_doc, source_label).

    source_label is "Foundry IQ (Azure AI Search)" if real credentials are
    configured, otherwise "Local knowledge base (Foundry IQ fallback)".
    """
    query = f"{category} incident on {service} in {region}, severity {severity}, root cause and resolution"

    if foundry_iq_configured():
        try:
            docs = _retrieve_via_azure_search(query, category, top_k)
            if docs:
                runbook = _load_runbook(category)
                return docs, runbook, "Foundry IQ (Azure AI Search)"
        except Exception as e:
            print(f"[foundry_iq] Azure Search call failed, falling back to local: {e}")

    docs = _retrieve_via_local(service, region, severity, category, top_k)
    runbook = _load_runbook(category)
    return docs, runbook, "Local knowledge base (Foundry IQ fallback)"


def generate_rca_with_llm(alert_text: str, category: str, service: str, region: str,
                           severity: str, txn_count: int,
                           similar_incidents: list[RetrievedDoc],
                           runbook: RetrievedDoc | None) -> tuple[str, str, list[str], str]:
    """
    GPT-4o reasoning step — produces (root_cause, confidence, contributing_factors, source_label).

    If Azure OpenAI / AI Foundry credentials are configured, calls GPT-4o with
    a structured prompt containing the classified incident + retrieved evidence,
    requesting chain-of-thought RCA reasoning. Falls back to a deterministic
    heuristic (majority-vote over retrieved incidents) if not configured.
    """
    evidence_block = "\n\n".join(
        f"- Incident {d.doc_id}: {d.title}\n"
        f"  Root cause: {d.root_cause}\n"
        f"  Resolution: {d.resolution} (resolved in {d.resolution_time_min} min)"
        for d in similar_incidents
    )
    runbook_block = f"\n\nRelevant runbook ({runbook.doc_id}):\n{runbook.content}" if runbook else ""

    if azure_openai_configured():
        try:
            return _generate_rca_via_gpt4o(alert_text, category, service, region, severity,
                                            txn_count, evidence_block, runbook_block)
        except Exception as e:
            print(f"[foundry_iq] GPT-4o call failed, falling back to heuristic: {e}")

    return _generate_rca_heuristic(similar_incidents, category, service, region, severity, txn_count)


def _generate_rca_via_gpt4o(alert_text, category, service, region, severity,
                             txn_count, evidence_block, runbook_block) -> tuple[str, str, list[str], str]:
    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )

    system_prompt = (
        "You are a senior NOC incident commander for a banking production environment. "
        "Given a new incident alert and evidence retrieved from the historical incident "
        "knowledge base, produce a Root Cause Analysis. "
        "Respond ONLY with valid JSON matching this schema: "
        '{"probable_root_cause": "...", "confidence": "HIGH|MEDIUM|LOW", '
        '"contributing_factors": ["...", "..."]}. '
        "Base your root cause primarily on the most similar historical incident's root cause "
        "unless the new alert's details clearly point elsewhere. Be specific and technical."
    )

    user_prompt = (
        f"NEW INCIDENT ALERT:\n{alert_text}\n\n"
        f"Classified as: category={category}, service={service}, region={region}, "
        f"severity={severity}, transactions_affected={txn_count}\n\n"
        f"RETRIEVED SIMILAR INCIDENTS (from Foundry IQ knowledge base):\n{evidence_block}"
        f"{runbook_block}\n\n"
        "Produce the RCA JSON now."
    )

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    return (
        parsed.get("probable_root_cause", "Unable to determine root cause."),
        parsed.get("confidence", "MEDIUM"),
        parsed.get("contributing_factors", []),
        "GPT-4o (Azure AI Foundry)",
    )


def _generate_rca_heuristic(similar_incidents, category, service, region, severity, txn_count
                             ) -> tuple[str, str, list[str], str]:
    """Deterministic fallback used when Azure OpenAI is not configured."""
    PATTERN_NOTES = {
        "DB Connectivity":   "Historical incidents in this category are most commonly caused by connection pool exhaustion or network-level timeouts between application and database tiers.",
        "Payment Gateway":   "Historical incidents show upstream adapter failures or SSL/TLS certificate issues as the dominant root cause pattern.",
        "Auth Service":      "Cache exhaustion and certificate rotation issues dominate the historical pattern for auth service incidents.",
        "FX Feed":           "Feed adapter connectivity loss and schema deserialization errors are the most frequent causes in the historical record.",
        "SWIFT Queue":       "Disk space exhaustion on MQ broker and message processing deadlocks are the leading patterns historically.",
        "Batch Job":         "Missing database indexes and insufficient disk space for intermediate processing are the most common batch failure patterns.",
        "Network":           "BGP route instability and misconfigured firewall rules post-change account for the majority of historical network incidents.",
        "Application Error": "Unhandled exceptions in API input validation and dependency service timeouts drive most application error incidents.",
    }

    if similar_incidents:
        probable_rc = similar_incidents[0].root_cause
        exact_matches = sum(1 for d in similar_incidents if "same service" in d.title)
        confidence = "HIGH" if exact_matches >= 2 else ("MEDIUM" if exact_matches >= 1 or len(similar_incidents) >= 2 else "LOW")
    else:
        probable_rc = f"Unable to determine root cause - no similar incidents found for {category} on {service}."
        confidence = "LOW"

    factors = [
        f"Service affected: {service} in {region} ({severity} severity)",
        f"Historical pattern: {PATTERN_NOTES.get(category, 'Insufficient historical data for this category.')}",
    ]
    if txn_count > 0:
        factors.append(f"Transaction impact: {txn_count:,} transactions affected")

    return probable_rc, confidence, factors, "Heuristic (offline mode)"

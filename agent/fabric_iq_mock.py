"""
Fabric IQ Ontology — Service / Team / SLA / Compliance Knowledge Graph
=========================================================================
In a full production deployment, this ontology would live in Microsoft Fabric
as a semantic model (OneLake + Power BI semantic layer), queried at runtime via
the Fabric IQ API so agents can reason over real business concepts: which team
owns a service, what the SLA is, and which regulatory thresholds apply.

For the hackathon, this module represents that semantic layer as a structured
Python knowledge graph. The shape mirrors what a Fabric IQ ontology query would
return (entity -> relationships -> attributes), so swapping in a live Fabric IQ
client later is a drop-in replacement of `get_service_context()`.
"""

from dataclasses import dataclass


# ── SLA policy (business rules — would live in Fabric semantic model) ──────────

SLA_POLICY = {
    "P1": {"target_minutes": 30, "description": "Critical — production down, customer impact"},
    "P2": {"target_minutes": 60, "description": "High — degraded service, partial impact"},
    "P3": {"target_minutes": 240, "description": "Medium — minor impact, workaround available"},
    "P4": {"target_minutes": 1440, "description": "Low — informational, no immediate impact"},
}

# MAS Technology Risk Management (TRM) — simplified reporting thresholds
MAS_TRM_POLICY = {
    "transaction_threshold": 500,
    "notification_window_minutes": 60,
    "regulation_ref": "MAS Notice 655 - Technology Risk Management",
    "description": (
        "Incidents affecting more than 500 customer transactions in production "
        "must be flagged for review under MAS Technology Risk Management "
        "guidelines, with notification to the compliance function within 60 minutes "
        "of detection."
    ),
}


# ── Service -> Team -> Assignee -> Runbook ontology ─────────────────────────────

FABRIC_IQ_ONTOLOGY = {
    "DB Connectivity": {
        "services": ["payment-db-sg-01", "core-banking-db-sg", "reporting-db-hk"],
        "team": "DB Operations Team",
        "assignee": "Priya Nair",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-DB-CONN-042",
        "escalation": "Head of DB Infrastructure",
        "business_criticality": "Tier 1 - directly supports payment settlement",
        "downstream_dependents": ["Payment Gateway", "Batch Job"],
    },
    "Payment Gateway": {
        "services": ["payment-gateway-sg", "payment-gateway-hk", "visa-adapter-sg"],
        "team": "Payments Platform Team",
        "assignee": "Rajan Kumar",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-PAY-GW-017",
        "escalation": "Head of Payments Engineering",
        "business_criticality": "Tier 1 - customer-facing payment settlement",
        "downstream_dependents": [],
    },
    "Auth Service": {
        "services": ["auth-service-sg", "oauth-provider-sg", "mfa-service-sg"],
        "team": "Identity & Access Team",
        "assignee": "Mei Lin",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-AUTH-SVC-031",
        "escalation": "CISO Office",
        "business_criticality": "Tier 1 - gates all customer login flows",
        "downstream_dependents": ["Application Error"],
    },
    "FX Feed": {
        "services": ["fx-rate-feed-apac", "reuters-adapter-sg", "bloomberg-feed-hk"],
        "team": "Market Data Team",
        "assignee": "Ahmed Hassan",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-FX-FEED-008",
        "escalation": "Head of Market Data",
        "business_criticality": "Tier 2 - required for FX trading and EOD batch",
        "downstream_dependents": ["Batch Job"],
    },
    "SWIFT Queue": {
        "services": ["swift-mq-sg-01", "swift-gateway-sg", "swift-ack-processor"],
        "team": "Messaging Infrastructure Team",
        "assignee": "Sanjay Patel",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-SWIFT-MQ-055",
        "escalation": "Head of Correspondent Banking",
        "business_criticality": "Tier 1 - correspondent banking settlement",
        "downstream_dependents": ["Batch Job"],
    },
    "Batch Job": {
        "services": ["eod-reconciliation", "trade-settlement-batch", "report-generation-job"],
        "team": "Batch Processing Team",
        "assignee": "Liu Wei",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-BATCH-EOD-023",
        "escalation": "Head of Operations",
        "business_criticality": "Tier 2 - regulatory reporting and reconciliation",
        "downstream_dependents": [],
    },
    "Network": {
        "services": ["vpc-sg-prod", "load-balancer-sg", "firewall-sg-01"],
        "team": "Network Operations Team",
        "assignee": "Farid Osman",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-NET-VPC-011",
        "escalation": "Head of Infrastructure",
        "business_criticality": "Tier 1 - underlies all production services",
        "downstream_dependents": ["DB Connectivity", "Payment Gateway", "FX Feed"],
    },
    "Application Error": {
        "services": ["mobile-banking-api", "internet-banking-sg", "teller-app-sg"],
        "team": "Application Support Team",
        "assignee": "Tanvi Sharma",
        "oncall_contact": "+65-9xxx-xxxx",
        "runbook_id": "RB-APP-ERR-044",
        "escalation": "Head of Digital Channels",
        "business_criticality": "Tier 1 - direct customer-facing channels",
        "downstream_dependents": [],
    },
}


@dataclass
class ServiceContext:
    category: str
    team: str
    assignee: str
    oncall_contact: str
    runbook_id: str
    escalation: str
    business_criticality: str
    downstream_dependents: list[str]
    sla_target_minutes: int
    sla_description: str


def get_service_context(category: str, severity: str) -> ServiceContext:
    """
    Fabric IQ semantic query - resolves a category + severity into full
    business context: ownership, escalation path, criticality, and SLA target.

    Drop-in replacement point: in a live deployment this function would call
    the Fabric IQ API (semantic model query over the Fabric ontology) instead
    of reading the local FABRIC_IQ_ONTOLOGY dict.
    """
    entry = FABRIC_IQ_ONTOLOGY.get(category)
    sla = SLA_POLICY.get(severity, SLA_POLICY["P3"])

    if entry is None:
        return ServiceContext(
            category=category,
            team="NOC Operations",
            assignee="NOC Lead (unresolved)",
            oncall_contact="N/A",
            runbook_id="RB-GENERIC-001",
            escalation="NOC Duty Manager",
            business_criticality="Unknown",
            downstream_dependents=[],
            sla_target_minutes=sla["target_minutes"],
            sla_description=sla["description"],
        )

    return ServiceContext(
        category=category,
        team=entry["team"],
        assignee=entry["assignee"],
        oncall_contact=entry["oncall_contact"],
        runbook_id=entry["runbook_id"],
        escalation=entry["escalation"],
        business_criticality=entry["business_criticality"],
        downstream_dependents=entry["downstream_dependents"],
        sla_target_minutes=sla["target_minutes"],
        sla_description=sla["description"],
    )


def check_mas_threshold(txn_count: int) -> tuple[bool, str]:
    """
    Fabric IQ business-rule query - checks transaction impact against the
    MAS Technology Risk Management reporting threshold.
    """
    threshold = MAS_TRM_POLICY["transaction_threshold"]
    if txn_count > threshold:
        note = (
            f"{txn_count:,} transactions affected exceeds the MAS TRM threshold "
            f"of {threshold:,} ({MAS_TRM_POLICY['regulation_ref']}). "
            f"Compliance notification required within "
            f"{MAS_TRM_POLICY['notification_window_minutes']} minutes of detection."
        )
        return True, note
    return False, ""

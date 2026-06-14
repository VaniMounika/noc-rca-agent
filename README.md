# 🔴 NOC Incident RCA Agent

> **Agents League Hackathon 2026 — Reasoning Agents Track**  
> An AI agent that ingests a banking production alert and produces a cited Root Cause Analysis report in seconds — replacing 30–45 minutes of manual investigation.

---

## 🎯 One-line pitch
Submit a banking production alert → get a cited, evidence-backed RCA report with compliance notification in under 10 seconds.

---

## 🏗 Microsoft IQ Integration

| IQ Layer | Role | Integration |
|---|---|---|
| **Foundry IQ** | Agentic knowledge retrieval — retrieves similar historical incidents and runbooks from Azure AI Search index | Real Azure AI Search index when credentials set; local fallback otherwise |
| **Fabric IQ** | Semantic ontology — resolves service → team → assignee → SLA → escalation path | Structured knowledge graph mirroring Fabric IQ semantic model shape |

---

## 🧠 Five-step reasoning chain

```
Raw alert
   ↓
[1] Classify      — category, severity, service, region, txn count
   ↓
[2] Correlate     — Foundry IQ retrieves top-3 similar incidents + runbook
   ↓
[3] RCA Reason    — GPT-4o (Azure AI Foundry) chain-of-thought root cause
   ↓
[4] Recommend     — Fabric IQ ontology → assignee, runbook, SLA risk
   ↓
[5] Compliance    — MAS TRM agent → drafts regulatory notification if threshold exceeded
   ↓
Structured RCA Report (dashboard + PDF export) + Human approval gate
```

---

## 🖥 Dashboard

Two-panel Streamlit dashboard:
- **Left panel:** colour-coded incident list (P1🔴 / P2🟡 / P3🟢) — click any to load
- **Right panel:** live step-by-step reasoning progress → structured RCA output → one-click PDF export
- **Metrics bar:** historical incidents indexed, P1 count, avg resolution time, SLA breach rate
- **Integration status:** live badges showing Foundry IQ / GPT-4o connection status

---

## 🚀 Quick start (runs without Azure credentials)

```bash
# 1. Clone
git clone https://github.com/<your-username>/noc-rca-agent
cd noc-rca-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard (works offline with local fallback)
streamlit run ui/dashboard.py
```

The dashboard runs **fully offline** using a local 110-incident knowledge base and
heuristic reasoning. Connect Azure credentials to go live with real Foundry IQ + GPT-4o.

### Connect Azure AI Foundry (optional — for live IQ integration)

```bash
# 1. Copy env template
cp .env.example .env

# 2. Fill in your Azure credentials (see .env.example)

# 3. Create Foundry IQ index and upload knowledge base (run once)
python scripts/setup_foundry_iq_index.py

# 4. Run dashboard — integration status will show "Foundry IQ live"
streamlit run ui/dashboard.py
```

---

## 📁 Project structure

```
noc_rca_agent/
├── data/
│   └── incident_dataset.csv          # 110 synthetic banking NOC incidents
├── agent/
│   ├── orchestrator.py               # Five-tool reasoning chain (main agent)
│   ├── foundry_iq_client.py          # Foundry IQ: Azure AI Search + GPT-4o
│   └── fabric_iq_mock.py             # Fabric IQ: service/team/SLA ontology
├── knowledge_base/
│   └── runbooks/                     # 8 runbook markdown files (one per category)
│       ├── RB-DB-CONN-042.md
│       ├── RB-PAY-GW-017.md
│       ├── RB-AUTH-SVC-031.md
│       ├── RB-FX-FEED-008.md
│       ├── RB-SWIFT-MQ-055.md
│       ├── RB-BATCH-EOD-023.md
│       ├── RB-NET-VPC-011.md
│       └── RB-APP-ERR-044.md
├── ui/
│   └── dashboard.py                  # Streamlit two-panel dashboard
├── utils/
│   └── pdf_export.py                 # Audit-ready PDF RCA report generator
├── scripts/
│   └── setup_foundry_iq_index.py     # One-time Azure AI Search index setup
├── .streamlit/
│   └── config.toml                   # Streamlit theme
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🏦 Domain context
Built on 6+ years of real banking NOC experience (Crédit Agricole CIB · HSBC · Standard Chartered Bank, Singapore). Incident patterns, SLA terminology, MAS TRM compliance thresholds, SWIFT messaging, and banking service ontology reflect real-world operations — not generic enterprise templates.

---

## 🔒 Safety & Data

- All incident data is **synthetically generated** — no real bank data, no customer PII
- **Human approval gate** required before any ticket is assigned
- **MAS TRM compliance agent** (Tool 5) flags and drafts regulatory notifications when transaction volume exceeds 500
- Foundry IQ provides **cited, grounded retrieval** — every RCA cites its evidence sources

---

## 📊 Judging criteria alignment

| Criterion (weight) | How this project addresses it |
|---|---|
| Accuracy & Relevance (20%) | Real Foundry IQ Azure AI Search integration + Fabric IQ ontology; banking NOC domain specificity with 110-incident knowledge base + 8 runbooks |
| Reasoning & Multi-step (20%) | 5 chained tools with explicit intermediate outputs and live progress visible in the dashboard |
| Reliability & Safety (20%) | Cited evidence retrieval, human approval gate, MAS compliance agent, graceful offline fallback |
| UX & Presentation (15%) | Streamlit two-panel dashboard, metrics bar, live step progress, PDF export, integration status badges |
| Creativity & Originality (15%) | Only banking NOC RCA agent in the competition; MAS Compliance Agent (Tool 5) is a genuine regulatory differentiator |
| Community Vote (10%) | Demo video — P1 incident resolved in under 10 seconds vs 30–45 min manual |

---

## 🎬 Demo video
[Link to be added before submission]

---

## 👤 Author
**Vani Mounika** — Senior Java Developer, Singapore  
6+ years banking & financial services (Crédit Agricole CIB · HSBC · Standard Chartered Bank)  
[vanimounika.gumroad.com](https://vanimounika.gumroad.com)

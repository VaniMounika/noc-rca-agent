"""
NOC Incident RCA Agent - Streamlit Dashboard
===============================================
Two-panel layout: incident list (left) + RCA output (right)
Run with: streamlit run ui/dashboard.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import time
import tempfile
from agent.orchestrator import run_agent, integration_status
from utils.pdf_export import generate_rca_pdf

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NOC Incident RCA Agent",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .top-bar {
    background: linear-gradient(135deg, #1A478A 0%, #0F6E56 100%);
    color: white; padding: 14px 22px;
    border-radius: 10px; margin-bottom: 14px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .top-bar h2 { margin: 0; font-size: 19px; font-weight: 600; }
  .top-bar small { opacity: 0.85; font-size: 12px; }
  .status-chip {
    font-size: 11px; padding: 3px 10px; border-radius: 20px; font-weight: 600;
    display: inline-block; margin-left: 6px;
  }
  .chip-live   { background: #2ECC71; color: #fff; }
  .chip-mock   { background: #F1C40F; color: #4A3B00; }

  .metric-row { display: flex; gap: 10px; margin-bottom: 14px; }
  .metric-card {
    flex: 1; background: var(--background-color, #fff);
    border: 1px solid #E0DDD6; border-radius: 10px; padding: 10px 14px;
  }
  .metric-num { font-size: 22px; font-weight: 700; color: #1A478A; }
  .metric-label { font-size: 11px; color: #888; margin-top: 2px; }

  .sev-p1 { background: #FCEBEB; color: #A32D2D; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; }
  .sev-p2 { background: #FAEEDA; color: #7A4800; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; }
  .sev-p3 { background: #EAF3DE; color: #3B6D11; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; }
  .sev-p4 { background: #F1EFE8; color: #555550; padding: 2px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; }

  .risk-critical { color: #A32D2D; font-weight: 800; font-size: 16px; }
  .risk-high     { color: #C77000; font-weight: 800; font-size: 16px; }
  .risk-medium   { color: #3B6D11; font-weight: 800; font-size: 16px; }
  .risk-low      { color: #1A478A; font-weight: 800; font-size: 16px; }

  .step-pill { font-size: 12px; padding: 4px 10px; border-radius: 14px; font-weight: 600; margin-right: 4px; }
  .step-done { background: #E1F5EE; color: #0F6E56; }
  .step-arrow { color: #bbb; font-size: 13px; margin: 0 2px; }

  .mas-flag {
    background: #FCEBEB; border: 1px solid #E5A0A0;
    border-radius: 8px; padding: 10px 14px; margin-top: 8px;
  }
  .source-tag {
    font-size: 10px; color: #888; font-style: italic; margin-top: -4px; margin-bottom: 6px;
  }
  div[data-testid="stHorizontalBlock"] { gap: 0.6rem; }
</style>
""", unsafe_allow_html=True)

# ── Integration status ───────────────────────────────────────────────────────
status = integration_status()
foundry_live = "Connected" in status["foundry_iq"]
gpt4o_live = "Connected" in status["gpt4o"]

foundry_chip = '<span class="status-chip chip-live">● Foundry IQ live</span>' if foundry_live \
    else '<span class="status-chip chip-mock">○ Foundry IQ fallback</span>'
gpt4o_chip = '<span class="status-chip chip-live">● GPT-4o live</span>' if gpt4o_live \
    else '<span class="status-chip chip-mock">○ Heuristic reasoning</span>'

# ── Top bar ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="top-bar">
  <div>
    <h2>🔴 NOC Incident RCA Agent</h2>
    <small>Banking Operations Intelligence &nbsp;·&nbsp; Foundry IQ + Fabric IQ + GPT-4o</small>
  </div>
  <div>{foundry_chip}{gpt4o_chip}</div>
</div>
""", unsafe_allow_html=True)

# ── Metrics bar ────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/incident_dataset.csv")

@st.cache_data
def load_stats():
    df = pd.read_csv(DATA_PATH)
    return {
        "total": len(df),
        "p1_count": len(df[df["severity"] == "P1"]),
        "avg_resolution": round(df["resolution_time_min"].mean()),
        "sla_breach_pct": round(100 * len(df[df["sla_breach"] == "Yes"]) / len(df)),
    }

stats = load_stats()

m1, m2, m3, m4 = st.columns(4)
for col, num, label in [
    (m1, stats["total"], "Historical incidents indexed"),
    (m2, stats["p1_count"], "P1 incidents on record"),
    (m3, f"{stats['avg_resolution']} min", "Avg manual resolution time"),
    (m4, f"{stats['sla_breach_pct']}%", "Historical SLA breach rate"),
]:
    with col:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-num">{num}</div>
            <div class="metric-label">{label}</div>
        </div>""", unsafe_allow_html=True)

st.write("")

# ── Demo incidents ─────────────────────────────────────────────────────────
DEMO_INCIDENTS = [
    {
        "id": "INC-20240603-001",
        "title": "Payment gateway timeout — prod SG",
        "severity": "P1",
        "time": "03:42 SGT",
        "alert": (
            "P1 CRITICAL — payment-gateway-sg is returning 503 for all settlement requests. "
            "847 txn affected. Singapore Production. Detected at 03:42 SGT. "
            "Upstream Visa adapter health check failing continuously."
        ),
    },
    {
        "id": "INC-20240603-002",
        "title": "FX rate feed delay — APAC markets",
        "severity": "P2",
        "time": "07:15 SGT",
        "alert": (
            "P2 DEGRADED — reuters-adapter-sg FX rate feed latency exceeded 5s SLA. "
            "Singapore Production. FX desk reporting stale rates. "
            "Detected at 07:15 SGT during APAC market open."
        ),
    },
    {
        "id": "INC-20240603-003",
        "title": "Auth service 503 — mobile banking",
        "severity": "P2",
        "time": "09:03 SGT",
        "alert": (
            "P2 — auth-service-sg returning 503 for mobile banking login requests. "
            "Singapore Production. Intermittent failures — 40% of login attempts failing. "
            "Redis cache memory usage at 98%."
        ),
    },
    {
        "id": "INC-20240603-004",
        "title": "EOD reconciliation batch failure",
        "severity": "P3",
        "time": "11:30 SGT",
        "alert": (
            "P3 — eod-reconciliation batch job failed at step 3 of 7. "
            "Singapore Production. Job timed out after 180 minutes. "
            "Error: query execution exceeded 30s limit on trade_summary table."
        ),
    },
    {
        "id": "INC-20240603-005",
        "title": "SWIFT message queue backlog",
        "severity": "P2",
        "time": "13:22 SGT",
        "alert": (
            "P2 — swift-mq-sg-01 message queue backlog growing. "
            "1,200 unprocessed outbound SWIFT messages. Singapore Production. "
            "ACK processor thread count dropped to 0. Disk usage at 89%. "
            "Approximately 620 customer payment instructions affected."
        ),
    },
]

# ── Session state ──────────────────────────────────────────────────────────
for key, default in [("selected_idx", 0), ("report", None), ("approved", False), ("custom_alert", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Layout ─────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 2.6])

# ── LEFT PANEL ─────────────────────────────────────────────────────────────
with col_left:
    st.markdown("**📋 Today's Incidents**")

    for i, inc in enumerate(DEMO_INCIDENTS):
        sev = inc["severity"]
        icon = "🔴" if sev == "P1" else ("🟡" if sev == "P2" else "🟢")
        label = f"{icon} **{inc['title']}**\n\n`{inc['id']}` · {inc['time']} · {sev}"
        if st.button(label, key=f"inc_{i}", use_container_width=True):
            st.session_state.selected_idx = i
            st.session_state.report = None
            st.session_state.approved = False
            st.rerun()

    st.divider()
    st.markdown("**➕ Custom alert**")
    custom = st.text_area(
        "Paste any alert text",
        height=110,
        placeholder="P1 — payment-gateway-sg down, 1200 txn affected...",
        label_visibility="collapsed",
    )
    if st.button("▶ Run agent on custom alert", use_container_width=True, type="primary"):
        if custom.strip():
            st.session_state.custom_alert = custom
            st.session_state.selected_idx = -1
            st.session_state.report = None
            st.session_state.approved = False
            st.rerun()

    st.divider()
    with st.expander("ℹ️ Integration status"):
        st.markdown(f"**Foundry IQ:** {status['foundry_iq']}")
        st.markdown(f"**GPT-4o:** {status['gpt4o']}")
        st.caption(
            "Running in fallback mode uses a local knowledge base and heuristic "
            "reasoning that mirrors live Foundry IQ + GPT-4o behaviour. "
            "Connect Azure credentials in `.env` to go live — see README."
        )

# ── RIGHT PANEL ────────────────────────────────────────────────────────────
with col_right:
    if st.session_state.selected_idx == -1:
        active = {"id": "CUSTOM", "title": "Custom alert", "severity": "P2",
                  "time": "now", "alert": st.session_state.custom_alert}
    else:
        active = DEMO_INCIDENTS[st.session_state.selected_idx]

    sev = active["severity"]
    h1, h2 = st.columns([5, 1])
    with h1:
        st.markdown(f"### {active['title']}")
        st.markdown(f"`{active['id']}` &nbsp; <span class='sev-{sev.lower()}'>{sev}</span> &nbsp; {active['time']}", unsafe_allow_html=True)
    with h2:
        st.write("")

    with st.container(border=True):
        st.markdown(f"**📨 Alert:** {active['alert']}")

    if st.session_state.report is None:
        st.write("")
        if st.button("▶ Analyse with RCA Agent", type="primary", use_container_width=True):
            progress = st.empty()

            step_msgs = [
                "🔵 **Step 1/5 — Classify:** Parsing alert, extracting category, severity, service, region...",
                "🔵 **Step 2/5 — Correlate:** Querying Foundry IQ knowledge base for similar historical incidents and runbooks...",
                "🔵 **Step 3/5 — RCA Reason:** Running chain-of-thought reasoning over classified incident + retrieved evidence...",
                "🔵 **Step 4/5 — Recommend:** Querying Fabric IQ ontology for service ownership, assignee, SLA target...",
                "🔵 **Step 5/5 — Compliance:** Checking MAS Technology Risk Management transaction threshold...",
            ]
            for msg in step_msgs:
                progress.markdown(msg)
                time.sleep(0.55)

            report = run_agent(active["alert"], active["title"])
            st.session_state.report = report
            st.session_state.approved = False
            progress.empty()
            st.rerun()
    else:
        report = st.session_state.report

        # Step summary
        steps_html = "".join(
            f'<span class="step-pill step-done">✅ {s}</span>' +
            ('<span class="step-arrow">›</span>' if i < 4 else "")
            for i, s in enumerate(["Classify", "Correlate", "RCA Reason", "Recommend", "Compliance"])
        )
        st.markdown(steps_html, unsafe_allow_html=True)
        st.write("")

        c1, c2 = st.columns(2)

        with c1:
            with st.container(border=True):
                st.markdown("**🏷 Classification**")
                st.markdown(f"**Category:** {report.classify.category}")
                st.markdown(f"**Service:** `{report.classify.service}`")
                st.markdown(f"**Region:** {report.classify.region} · {report.classify.environment}")
                if report.classify.txn_count:
                    st.markdown(f"**Txn affected:** {report.classify.txn_count:,}")
                st.markdown(f"**Classification confidence:** {report.classify.confidence:.0%}")

        with c2:
            with st.container(border=True):
                st.markdown("**⚠️ SLA & Assignment**")
                risk = report.recommend.sla_risk
                risk_class = f"risk-{risk.lower()}"
                st.markdown(f"**SLA risk:** <span class='{risk_class}'>{risk}</span> &nbsp; (target: {report.recommend.sla_target_minutes} min)", unsafe_allow_html=True)
                st.markdown(f"**Assignee:** {report.recommend.assignee}")
                st.markdown(f"**Team:** {report.recommend.team}")
                st.markdown(f"**Escalation:** {report.recommend.escalation}")
                st.markdown(f"**Criticality:** {report.recommend.business_criticality}")

        with st.container(border=True):
            st.markdown("**🔍 Root Cause Analysis**")
            st.markdown(f"<div class='source-tag'>Reasoning engine: {report.rca.reasoning_source}</div>", unsafe_allow_html=True)
            st.markdown(f"**Probable root cause:** {report.rca.probable_root_cause}")
            st.markdown(f"**Confidence:** `{report.rca.confidence}`")
            st.markdown(f"**Evidence citations:** {', '.join(report.rca.evidence_citations) or 'N/A'}")
            st.markdown("**Contributing factors:**")
            for f in report.rca.contributing_factors:
                st.markdown(f"- {f}")

        with st.container(border=True):
            st.markdown("**📚 Similar Past Incidents**")
            st.markdown(f"<div class='source-tag'>Source: {report.correlate.source}</div>", unsafe_allow_html=True)
            for s in report.correlate.similar_incidents:
                with st.expander(f"{s.incident_id} · {s.similarity_note}"):
                    st.markdown(f"**Root cause:** {s.root_cause}")
                    st.markdown(f"**Resolution:** {s.resolution}")
                    st.markdown(f"**Resolved in:** {s.resolution_time_min} min")
            if report.correlate.runbook_excerpt:
                with st.expander(f"📄 Runbook {report.correlate.runbook_id} (excerpt)"):
                    st.markdown(report.correlate.runbook_excerpt)

        with st.container(border=True):
            st.markdown("**🛠 Recommended Actions**")
            for i, step in enumerate(report.recommend.remediation_steps, 1):
                if step:
                    st.markdown(f"{i}. {step}.")

        if report.compliance.mas_flag:
            with st.container(border=True):
                st.markdown("**🚨 MAS Compliance Notification (Draft)**")
                st.markdown(
                    "<div class='mas-flag'>Transaction impact exceeds MAS Technology Risk Management "
                    "reporting threshold. A draft notification has been prepared for the compliance team.</div>",
                    unsafe_allow_html=True,
                )
                with st.expander("View draft notification"):
                    st.code(report.compliance.notification_draft, language=None)

        st.divider()

        b1, b2, b3 = st.columns(3)

        with b1:
            if not st.session_state.approved:
                if st.button(f"✅ Approve & assign to {report.recommend.assignee.split()[0]}", type="primary", use_container_width=True):
                    st.session_state.approved = True
                    st.rerun()
            else:
                st.success(f"✅ Assigned to {report.recommend.assignee} — human approval recorded")

        with b2:
            try:
                tmp_path = os.path.join(tempfile.gettempdir(), f"RCA_{active['id']}.pdf")
                generate_rca_pdf(report, tmp_path)
                with open(tmp_path, "rb") as f:
                    st.download_button(
                        "📄 Export RCA (PDF)",
                        f.read(),
                        file_name=f"RCA_{active['id']}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"PDF export error: {e}")

        with b3:
            if st.button("🔄 Re-run agent", use_container_width=True):
                st.session_state.report = None
                st.session_state.approved = False
                st.rerun()

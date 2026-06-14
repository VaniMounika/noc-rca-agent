"""
RCA PDF Export
================
Generates an audit-ready PDF version of an RCA report using fpdf2.
"""

from fpdf import FPDF
from datetime import datetime


ACCENT = (26, 71, 138)       # #1A478A
ACCENT2 = (15, 110, 86)      # #0F6E56
GRAY = (90, 90, 90)
LIGHT_GRAY = (240, 240, 240)


class RCAPdf(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*ACCENT)
        self.cell(0, 8, "NOC Incident RCA Agent", ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GRAY)
        self.cell(0, 5, "Banking Operations Intelligence - Auto-Generated RCA Report", ln=True)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.5)
        self.line(10, 20, 200, 20)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Agents League Hackathon 2026 | Page {self.page_no()}", align="C")

    def section_title(self, text):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ACCENT2)
        self.set_fill_color(*LIGHT_GRAY)
        self.cell(0, 8, f"  {text}", ln=True, fill=True)
        self.ln(1)

    def field(self, label, value):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(60, 60, 60)
        self.cell(45, 6, label)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 6, _s(str(value)))

    def body_text(self, text):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(20, 20, 20)
        self.cell(5)
        self.multi_cell(0, 5.5, f"- {text}")


def generate_rca_pdf(report, output_path: str) -> str:
    """
    Generates a PDF RCA report from an RCAReport dataclass instance.
    Returns the output_path.
    """
    pdf = RCAPdf()
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, f"RCA Report: {report.incident_title}", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 6, f"Severity: {report.classify.severity}  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M SGT')}", ln=True)
    pdf.ln(3)

    # Raw alert
    pdf.section_title("Original Alert")
    pdf.body_text(report.raw_alert)
    pdf.ln(2)

    # Classification
    pdf.section_title("1. Classification")
    pdf.field("Category:", report.classify.category)
    pdf.field("Severity:", report.classify.severity)
    pdf.field("Service:", report.classify.service)
    pdf.field("Region:", f"{report.classify.region} ({report.classify.environment})")
    if report.classify.txn_count:
        pdf.field("Transactions affected:", f"{report.classify.txn_count:,}")
    pdf.field("Classification confidence:", f"{report.classify.confidence:.0%}")
    pdf.ln(2)

    # Correlate
    pdf.section_title("2. Correlated Historical Incidents (Foundry IQ)")
    pdf.field("Source:", report.correlate.source)
    pdf.field("Runbook:", report.correlate.runbook_id)
    for s in report.correlate.similar_incidents:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"{s.incident_id} ({s.similarity_note})", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5.5, f"Root cause: {s.root_cause}")
        pdf.multi_cell(0, 5.5, f"Resolution: {s.resolution} (resolved in {s.resolution_time_min} min)")
        pdf.ln(1)
    pdf.ln(1)

    # RCA Reasoning
    pdf.section_title("3. Root Cause Analysis")
    pdf.field("Reasoning engine:", report.rca.reasoning_source)
    pdf.field("Confidence:", report.rca.confidence)
    pdf.body_text(f"Probable root cause: {report.rca.probable_root_cause}")
    pdf.field("Evidence citations:", ", ".join(report.rca.evidence_citations) or "N/A")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "Contributing factors:", ln=True)
    for f in report.rca.contributing_factors:
        pdf.bullet(f)
    pdf.ln(2)

    # Recommendation
    pdf.section_title("4. Recommendation (Fabric IQ)")
    pdf.field("Assignee:", f"{report.recommend.assignee} ({report.recommend.team})")
    pdf.field("Escalation contact:", report.recommend.escalation)
    pdf.field("Business criticality:", report.recommend.business_criticality)
    pdf.field("SLA risk:", report.recommend.sla_risk)
    pdf.field("SLA target:", f"{report.recommend.sla_target_minutes} minutes")
    pdf.field("Runbook:", report.recommend.runbook_id)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "Recommended remediation steps:", ln=True)
    for i, step in enumerate(report.recommend.remediation_steps, 1):
        if step:
            pdf.bullet(f"{i}. {step}")
    pdf.ln(2)

    # Compliance
    if report.compliance.mas_flag:
        pdf.section_title("5. MAS Compliance Notification (Draft)")
        pdf.set_text_color(160, 30, 30)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, "MAS TRM reporting threshold exceeded - draft notification generated.", ln=True)
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Courier", "", 8)
        pdf.multi_cell(0, 4.5, report.compliance.notification_draft)
        pdf.ln(2)

    # Approval section
    pdf.section_title("Approval")
    pdf.body_text(
        "This RCA was generated by an AI agent and requires human review before "
        "ticket assignment or regulatory submission. The NOC Incident RCA Agent "
        "augments human decision-making and does not act autonomously."
    )
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 6, "Reviewed by: _______________________")
    pdf.cell(95, 6, "Date: _______________________", ln=True)

    pdf.output(output_path)
    return output_path

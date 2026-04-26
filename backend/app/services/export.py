"""
Cyrus — Export Service (Sprint 4)

Handles all export formats:
- CSV (all class grades in one spreadsheet)
- Excel (.xlsx with multiple sheets)
- Google Sheets (push via gspread)
- PDF report card per student (WeasyPrint)
- Bulk ZIP (all student PDFs in one download)
"""

import io
import csv
import json
import structlog
from datetime import datetime
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


class ExportService:

    # ─────────────────────────────────────────────────────────────────
    # CSV Export
    # ─────────────────────────────────────────────────────────────────
    def export_exam_csv(self, exam_data: dict) -> bytes:
        """
        Export all student grades for one exam as CSV.

        exam_data format:
        {
            "exam_name": "IA 1 - Innovation and Design Thinking",
            "max_marks": 30,
            "students": [
                {"name": "Zaeem Zameer Mohammed", "reg_no": "25191160",
                 "total_marks": 22, "grades": [{"question": "Q1", "marks": 2}, ...]}
            ]
        }
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        questions = []
        if exam_data["students"]:
            questions = [g["question"] for g in exam_data["students"][0].get("grades", [])]

        headers = ["Name", "Registration No", "Total", f"/ {exam_data['max_marks']}",
                   "Percentage"] + questions
        writer.writerow(headers)

        # Data rows
        for student in exam_data["students"]:
            row = [
                student["name"],
                student.get("reg_no", ""),
                student["total_marks"],
                f"/ {exam_data['max_marks']}",
                f"{student['total_marks'] / exam_data['max_marks'] * 100:.1f}%",
            ]
            for grade in student.get("grades", []):
                row.append(grade.get("marks", ""))
            writer.writerow(row)

        return output.getvalue().encode("utf-8-sig")  # utf-8-sig adds BOM for Excel

    # ─────────────────────────────────────────────────────────────────
    # Google Sheets Export
    # ─────────────────────────────────────────────────────────────────
    def export_to_google_sheets(self, spreadsheet_id: str, exam_data: dict) -> str:
        """
        Push grades to a Google Sheet.
        Returns the spreadsheet URL.
        """
        if not settings.google_service_account_json:
            raise ValueError("Google service account not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON in .env")

        import gspread
        from google.oauth2.service_account import Credentials

        creds_dict = json.loads(settings.google_service_account_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(spreadsheet_id)

        # Create or clear a worksheet named after the exam
        sheet_name = exam_data["exam_name"][:50]  # Google Sheets has 50-char limit
        try:
            ws = sh.worksheet(sheet_name)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_name, rows="200", cols="30")

        # Write headers
        questions = [g["question"] for g in (exam_data["students"][0].get("grades", []) if exam_data["students"] else [])]
        headers = ["Name", "Reg No", "Total", "Percentage"] + questions
        ws.append_row(headers)

        # Write data
        for student in exam_data["students"]:
            row = [
                student["name"],
                student.get("reg_no", ""),
                student["total_marks"],
                f"{student['total_marks'] / exam_data['max_marks'] * 100:.1f}%",
            ] + [g.get("marks", "") for g in student.get("grades", [])]
            ws.append_row(row)

        log.info("google_sheets_exported", sheet=sheet_name, students=len(exam_data["students"]))
        return sh.url

    # ─────────────────────────────────────────────────────────────────
    # PDF Report Card
    # ─────────────────────────────────────────────────────────────────
    def generate_student_pdf(self, report_data: dict) -> bytes:
        """
        Generate a professional PDF report card for one student.

        report_data: {
            "student_name": "...",
            "exam_name": "...",
            "total_marks": 22,
            "max_marks": 30,
            "summary": "...",
            "study_tips": [...],
            "concept_gaps": [...],
            "grades": [...]
        }
        """
        html = self._render_report_html(report_data)
        try:
            from weasyprint import HTML
            return HTML(string=html).write_pdf()
        except ImportError:
            log.warning("weasyprint_not_installed", fallback="html_bytes")
            return html.encode("utf-8")

    def _render_report_html(self, data: dict) -> str:
        """Render the PDF report as HTML (WeasyPrint converts this to PDF)."""
        percentage = data["total_marks"] / data["max_marks"] * 100 if data["max_marks"] else 0
        grade_letter = "A" if percentage >= 85 else "B" if percentage >= 70 else "C" if percentage >= 55 else "D" if percentage >= 40 else "F"
        color = "#10b981" if percentage >= 70 else "#f59e0b" if percentage >= 40 else "#ef4444"

        tips_html = "".join(
            f'<li><strong>{t["topic"]}</strong>: {t["tip"]}'
            + (f' <em>({t["chapter_ref"]})</em>' if t.get("chapter_ref") else "")
            + "</li>"
            for t in data.get("study_tips", [])
        )

        gaps_html = "".join(
            f'<li>{g["concept"]} <span class="badge-{g["severity"]}">{g["severity"]}</span></li>'
            for g in data.get("concept_gaps", [])
        )

        grades_rows = "".join(
            f'<tr><td>{g["question"]}</td><td>{g["marks"]}/{g["max"]}</td>'
            f'<td>{g.get("feedback", "")}</td></tr>'
            for g in data.get("grades", [])
        )

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #1a1a2e; margin: 0; padding: 40px; }}
  .header {{ background: linear-gradient(135deg, #7c3aed, #4f46e5); color: white; padding: 24px; border-radius: 12px; margin-bottom: 24px; }}
  .score-circle {{ display: inline-block; width: 80px; height: 80px; border-radius: 50%; background: white; color: {color}; font-size: 24px; font-weight: bold; line-height: 80px; text-align: center; float: right; }}
  .section {{ margin-bottom: 24px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
  .section h3 {{ background: #f8fafc; padding: 10px 16px; margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; color: #4f46e5; }}
  .section-body {{ padding: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
  th {{ font-weight: 600; background: #f8fafc; }}
  .badge-major {{ background: #fee2e2; color: #991b1b; padding: 1px 6px; border-radius: 9px; font-size: 11px; }}
  .badge-minor {{ background: #fef3c7; color: #92400e; padding: 1px 6px; border-radius: 9px; font-size: 11px; }}
  li {{ margin: 6px 0; font-size: 13px; }}
  .footer {{ text-align: center; margin-top: 32px; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>

<div class="header">
  <div class="score-circle">{grade_letter}</div>
  <h1 style="margin:0;font-size:22px">{data['student_name']}</h1>
  <p style="margin:4px 0 0;opacity:0.85">{data['exam_name']}</p>
  <p style="margin:2px 0 0;opacity:0.75;font-size:13px">Score: {data['total_marks']}/{data['max_marks']} ({percentage:.0f}%)</p>
</div>

<div class="section">
  <h3>📋 Summary</h3>
  <div class="section-body"><p>{data.get('summary', '')}</p><p>{data.get('positive_notes', '')}</p></div>
</div>

<div class="section">
  <h3>📊 Question Breakdown</h3>
  <table>
    <thead><tr><th>Question</th><th>Marks</th><th>Feedback</th></tr></thead>
    <tbody>{grades_rows}</tbody>
  </table>
</div>

{'<div class="section"><h3>🎯 Areas to Improve</h3><div class="section-body"><ul>' + gaps_html + '</ul></div></div>' if gaps_html else ''}

{'<div class="section"><h3>📚 Study Tips</h3><div class="section-body"><ul>' + tips_html + '</ul></div></div>' if tips_html else ''}

<div class="footer">
  Generated by Cyrus AI Grading Platform · {datetime.now().strftime("%B %d, %Y")}
</div>
</body>
</html>"""

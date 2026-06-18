import re
from io import BytesIO

from xhtml2pdf import pisa

PDF_STYLES = """
@page {
  size: A4;
  margin: 1.2cm 1.4cm;
}
body {
  font-family: Helvetica, Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.3;
  color: #0f172a;
  margin: 0;
  padding: 0;
}
h1 {
  font-size: 15pt;
  border-bottom: 1.5pt solid #1d4ed8;
  padding-bottom: 3pt;
  margin: 0 0 5pt 0;
}
h2 {
  font-size: 11.5pt;
  color: #1e40af;
  margin: 8pt 0 3pt 0;
}
h3 {
  font-size: 10pt;
  color: #334155;
  margin: 6pt 0 2pt 0;
}
p {
  margin: 2pt 0;
}
ul {
  margin: 2pt 0 4pt 0;
  padding-left: 12pt;
}
li {
  margin-bottom: 1pt;
}
blockquote {
  background: #f0f9ff;
  border-left: 2.5pt solid #3b82f6;
  padding: 4pt 7pt;
  margin: 4pt 0;
  font-size: 9pt;
  color: #334155;
}
hr {
  border: none;
  border-top: 0.5pt solid #e2e8f0;
  margin: 6pt 0;
}
.footer {
  color: #64748b;
  font-size: 8pt;
  margin-top: 8pt;
}
strong {
  color: #0f172a;
}
"""


def safe_filename(title: str) -> str:
    name = re.sub(r"[^\w\s-]", "", title.replace("—", "-"))
    name = re.sub(r"\s+", "-", name.strip())
    return (name[:80] or "report").lower()


def _apply_pdf_styles(html: str) -> str:
    return re.sub(
        r"<style>.*?</style>",
        f"<style>{PDF_STYLES}</style>",
        html,
        count=1,
        flags=re.DOTALL,
    )


def html_to_pdf(html: str) -> bytes:
    """Convert report HTML to PDF bytes."""
    html = _apply_pdf_styles(html)

    buffer = BytesIO()
    status = pisa.CreatePDF(html, dest=buffer, encoding="utf-8")
    if status.err:
        raise ValueError("PDF generation failed")
    return buffer.getvalue()

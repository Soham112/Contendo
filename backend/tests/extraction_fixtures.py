"""Builds the PDF and DOCX inputs the extraction tests read, so no binary file
is committed. make_pdf writes a minimal PDF by hand (Helvetica text at given
heights); pypdf (BSD, test-only) encrypts one."""
from __future__ import annotations

import io
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "extraction"
PAGE_HEIGHT = 792


def jina(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[tuple[float, str]]]) -> bytes:
    """pages: per page, (height from the bottom, text) lines."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        stream = "BT /F1 11 Tf " + " ".join(f"1 0 0 1 72 {y} Tm ({_escape(t)}) Tj" for y, t in lines) + " ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content_id = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 {PAGE_HEIGHT}] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def report_pdf(n_pages: int = 4) -> bytes:
    """Pages with a running header, a page-number footer and two body paragraphs;
    page 2's first paragraph ends in a hyphenated word."""
    pages = []
    for p in range(1, n_pages + 1):
        body_word = "deploy-" if p == 2 else f"section{p}"
        pages.append([
            (770, "Acme Quarterly Report"),                       # running header
            (700, f"Paragraph one of page {p} talks about {body_word}"),
            (686, "ment of the pipeline and what changed." if p == 2 else "the next line of paragraph one."),
            (640, f"Paragraph two of page {p} starts after a gap."),
            (30, f"Page {p} of {n_pages}"),                       # page-number footer
        ])
    return make_pdf(pages)


def encrypted(pdf: bytes, password: str = "secret") -> bytes:
    from pypdf import PdfReader, PdfWriter
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    writer.encrypt(user_password=password, owner_password=password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_docx() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_heading("Launch plan", level=0)            # style "Title"
    doc.add_heading("Goals", level=1)
    doc.add_paragraph("Ship the importer by May.")
    table = doc.add_table(rows=2, cols=2)
    for r, (a, b) in enumerate([("Owner", "Due"), ("Priya", "May 3")]):
        table.cell(r, 0).text, table.cell(r, 1).text = a, b
    doc.add_paragraph("Ok.")                           # short lines are content too
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()

"""An uploaded file: PDF (pdfplumber, MIT), DOCX (python-docx, MIT), TXT, Markdown.

PDF: running headers, footers and page numbers are lines in the top or bottom
band of the page whose text, with digits masked, repeats on most pages; they
are removed by that position and repetition, not by their words. Paragraphs
are rebuilt from vertical gaps; a word hyphenated across a line break is
joined. A PDF with almost no text layer is a scanned image and is refused.
DOCX: heading styles become `#` headings, tables become `a | b` rows, in
document order. The title is the filename (a PDF's or DOCX's metadata title is
often a template leftover).
"""
from __future__ import annotations

import io
import re
from collections import Counter
from pathlib import Path

from extractors import Extraction, ExtractionError
from extractors.markdown import normalize_markdown
from memory.source_store import uploaded

VERSION = "2"   # 2: pdfplumber with header/footer removal and paragraphs; DOCX headings and tables; .md
SUPPORTED = (".pdf", ".docx", ".txt", ".md")
SCANNED_MESSAGE = "This PDF is a scanned image. Upload a text PDF or a photo of the page instead."
_MIN_PDF_CHARS = 100
_BAND = 0.08            # top and bottom 8% of the page height
_REPEAT_SHARE = 0.5     # a band line on at least half the pages (and 3 or more) is a running header/footer
_DIGITS = re.compile(r"\d+")


def _pdf_lines(file_bytes: bytes) -> list[list[dict]]:
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                lines = page.extract_text_lines(return_chars=False) or []
                pages.append([{"text": l["text"].strip(), "top": l["top"], "bottom": l["bottom"],
                               "band": l["top"] < page.height * _BAND or l["bottom"] > page.height * (1 - _BAND)}
                              for l in lines if l["text"].strip()])
            return pages
    except PDFPasswordIncorrect:
        raise ExtractionError("PDF is password-protected and cannot be read.")
    except Exception:
        raise ExtractionError("Could not open this PDF. It may be damaged.")


def _running_lines(pages: list[list[dict]]) -> set[str]:
    if len(pages) < 3:
        return set()
    seen = Counter()
    for lines in pages:
        seen.update({_DIGITS.sub("#", l["text"]) for l in lines if l["band"]})
    return {key for key, n in seen.items() if n >= max(3, len(pages) * _REPEAT_SHARE)}


def _paragraphs(lines: list[dict]) -> list[str]:
    if not lines:
        return []
    gaps = [b["top"] - a["bottom"] for a, b in zip(lines, lines[1:]) if b["top"] > a["bottom"]]
    typical = sorted(gaps)[(len(gaps) - 1) // 2] if gaps else 0   # lower median: the line spacing
    paragraphs, current = [], lines[0]["text"]
    for prev, line in zip(lines, lines[1:]):
        if line["top"] - prev["bottom"] > max(typical * 1.5, 2):
            paragraphs.append(current)
            current = line["text"]
        elif current.endswith("-") and line["text"][:1].islower():
            current = current[:-1] + line["text"]
        else:
            current = f"{current} {line['text']}"
    paragraphs.append(current)
    return paragraphs


def extract_pdf(file_bytes: bytes) -> str:
    pages = _pdf_lines(file_bytes)
    running = _running_lines(pages)
    blocks = []
    for lines in pages:
        kept = [l for l in lines if not (l["band"] and _DIGITS.sub("#", l["text"]) in running)]
        blocks += _paragraphs(kept)
    text = "\n\n".join(blocks).strip()
    if len(text) < _MIN_PDF_CHARS:
        raise ExtractionError(SCANNED_MESSAGE)
    return text


def extract_docx(file_bytes: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception:
        raise ExtractionError("Could not open this DOCX file. It may be damaged.")
    blocks = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name if para.style is not None else ""
            level = style.removeprefix("Heading ").strip() if style.startswith("Heading ") else ""
            if style == "Title":
                blocks.append(f"# {text}")
            elif level.isdigit():
                blocks.append(f"{'#' * min(int(level) + 1, 6)} {text}")
            else:
                blocks.append(text)
        elif child.tag.endswith("}tbl"):
            rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in Table(child, doc).rows]
            blocks.append("\n".join(r for r in rows if r.replace("|", "").strip()))
    text = "\n\n".join(b for b in blocks if b).strip()
    if not text:
        raise ExtractionError("DOCX file contains no readable text.")
    return text


def _decode(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def extract_file(filename: str, file_bytes: bytes, mime: str | None) -> Extraction:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ExtractionError(f"Unsupported file type: '{filename}'. Supported formats: PDF, DOCX, TXT, MD.")
    if suffix == ".pdf":
        text = extract_pdf(file_bytes)
    elif suffix == ".docx":
        text = extract_docx(file_bytes)
    elif suffix == ".md":
        text = normalize_markdown(_decode(file_bytes))
    else:
        text = _decode(file_bytes).strip()
    if not text:
        raise ExtractionError("This file is empty.")
    return Extraction(
        text=text,
        title=Path(filename).stem or filename,
        original=uploaded("file", data=file_bytes, mime=mime or "application/octet-stream",
                          extractor=(f"file_extractor{suffix}", VERSION), title_provided=True,
                          filename=filename),
    )

import io
from typing import IO


def extract_from_pdf(file_bytes: bytes) -> str:
    import fitz  # pymupdf

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}")

    if doc.is_encrypted:
        raise ValueError("PDF is password-protected and cannot be read.")

    pages_text: list[str] = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()

    text = "\n".join(pages_text).strip()
    if len(text) < 100:
        raise ValueError(
            "PDF appears to be scanned or image-only — no extractable text found."
        )
    return text


def extract_from_docx(file_bytes: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not open DOCX: {e}")

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise ValueError("DOCX file contains no readable text.")
    return text


def extract_from_txt(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1").strip()
    if not text:
        raise ValueError("Text file is empty.")
    return text


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Dispatch to the correct extractor based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_from_pdf(file_bytes)
    elif lower.endswith(".docx"):
        return extract_from_docx(file_bytes)
    elif lower.endswith(".txt"):
        return extract_from_txt(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type: '{filename}'. Supported formats: PDF, DOCX, TXT."
        )

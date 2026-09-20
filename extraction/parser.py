"""Extracts plain text from uploaded contract files (.txt, .docx, .pdf)."""

from pathlib import Path

import pypdf
from docx import Document

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}


class UnsupportedFileTypeError(Exception):
    """Raised when the file extension isn't one we know how to parse."""


class EmptyDocumentError(Exception):
    """Raised when the extracted text is empty or whitespace-only."""


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_docx(path: Path) -> str:
    document = Document(str(path))
    # Joined with blank lines (not a single "\n") so each Word paragraph becomes its own
    # paragraph downstream too - split_bilingual_contract's language-detection fallback
    # splits on blank lines, and a single "\n" join would collapse the whole document
    # into one undetectable block.
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_pdf(path: Path) -> str:
    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_file(file_path: str) -> str:
    """Extract plain text from a .txt, .docx, or .pdf file.

    Raises UnsupportedFileTypeError for any other extension, and EmptyDocumentError if
    the file parses but contains no usable text (e.g. a scanned PDF with no text layer).
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".txt":
        text = _extract_txt(path)
    elif extension == ".docx":
        text = _extract_docx(path)
    elif extension == ".pdf":
        text = _extract_pdf(path)
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension}'. Supported types: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    if not text or not text.strip():
        raise EmptyDocumentError(
            f"No extractable text found in '{path.name}'. If this is a scanned document, "
            "it needs OCR before it can be processed."
        )

    return text

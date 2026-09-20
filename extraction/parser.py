"""Extracts plain text from uploaded contract files (.txt, .docx, .pdf), falling back to
OCR (Arabic + English) for scanned PDFs with no embedded text layer.
"""

import os
from pathlib import Path
from typing import NamedTuple

import pypdf
import pytesseract
from docx import Document
from pdf2image import convert_from_path
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PopplerNotInstalledError,
)

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}

# Below this average characters-per-page, a PDF is treated as having no real text layer
# (i.e. scanned/image-based) rather than just being a short document.
MIN_CHARS_PER_PAGE = 20

pytesseract.pytesseract.tesseract_cmd = os.environ.get(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
# pdf2image needs poppler's pdftoppm/pdfinfo binaries, which - unlike Tesseract - aren't
# necessarily on PATH. Leave unset to rely on PATH (the normal case on Linux/Mac once
# poppler-utils is installed); set this to poppler's bin directory otherwise.
_POPPLER_PATH = os.environ.get("POPPLER_PATH") or None


class UnsupportedFileTypeError(Exception):
    """Raised when the file extension isn't one we know how to parse."""


class EmptyDocumentError(Exception):
    """Raised when the extracted text is empty or whitespace-only."""


class ScannedDocumentOCRError(Exception):
    """Raised when OCR itself fails, or produces no usable text, on a scanned PDF."""


class ExtractedDocument(NamedTuple):
    text: str
    extraction_method: str  # "direct" | "ocr"


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_docx(path: Path) -> str:
    document = Document(str(path))
    # Joined with blank lines (not a single "\n") so each Word paragraph becomes its own
    # paragraph downstream too - split_bilingual_contract's language-detection fallback
    # splits on blank lines, and a single "\n" join would collapse the whole document
    # into one undetectable block.
    return "\n\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_pdf(path: Path) -> tuple[str, int]:
    reader = pypdf.PdfReader(str(path))
    pages = reader.pages
    text = "\n".join(page.extract_text() or "" for page in pages)
    return text, len(pages)


def _looks_scanned(text: str, page_count: int) -> bool:
    if page_count <= 0:
        return True
    return len(text.strip()) < MIN_CHARS_PER_PAGE * page_count


def _ocr_pdf(path: Path) -> str:
    """OCR every page of a PDF with no usable text layer, recognizing Arabic and English
    together in a single pass (so mixed-language layout doesn't need to be known upfront).
    """
    try:
        images = convert_from_path(str(path), poppler_path=_POPPLER_PATH)
    except (PDFInfoNotInstalledError, PDFPageCountError, PopplerNotInstalledError) as exc:
        raise ScannedDocumentOCRError(
            f"OCR failed for '{path.name}': could not render PDF pages to images ({exc}). "
            "Poppler may not be installed or on PATH - set the POPPLER_PATH environment "
            "variable to its bin directory if needed."
        ) from exc

    pages_text = []
    for image in images:
        try:
            pages_text.append(pytesseract.image_to_string(image, lang="ara+eng"))
        except pytesseract.TesseractError as exc:
            raise ScannedDocumentOCRError(f"OCR failed for '{path.name}': {exc}") from exc

    text = "\n\n".join(pages_text)
    if not text.strip():
        raise ScannedDocumentOCRError(
            f"OCR ran on '{path.name}' but produced no usable text. The scan quality may be "
            "too low, or the document may not actually contain readable text."
        )
    return text


def extract_text_from_file(file_path: str) -> ExtractedDocument:
    """Extract plain text from a .txt, .docx, or .pdf file.

    For a .pdf with little to no embedded text (a scanned document), automatically falls
    back to OCR (Arabic + English). Returns both the text and which method produced it,
    since OCR accuracy is inherently lower and callers may want to surface that.

    Raises UnsupportedFileTypeError for any other extension, EmptyDocumentError if the
    file parses (or OCRs) but contains no usable text, and ScannedDocumentOCRError if OCR
    itself fails on a scanned PDF.
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    extraction_method = "direct"

    if extension == ".txt":
        text = _extract_txt(path)
    elif extension == ".docx":
        # .docx always has a real text layer - no OCR fallback applies here.
        text = _extract_docx(path)
    elif extension == ".pdf":
        text, page_count = _extract_pdf(path)
        if _looks_scanned(text, page_count):
            text = _ocr_pdf(path)
            extraction_method = "ocr"
    else:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension}'. Supported types: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    if not text or not text.strip():
        raise EmptyDocumentError(f"No extractable text found in '{path.name}'.")

    return ExtractedDocument(text=text, extraction_method=extraction_method)

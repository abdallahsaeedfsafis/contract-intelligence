"""Endpoint for uploading a new contract file (.txt/.docx/.pdf) into the pipeline."""

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException, UploadFile  # noqa: E402

from api.schemas import ContractUploadResponse  # noqa: E402
from extraction.extractor import split_bilingual_contract  # noqa: E402
from extraction.parser import (  # noqa: E402
    EmptyDocumentError,
    ScannedDocumentOCRError,
    UnsupportedFileTypeError,
    extract_text_from_file,
)

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"
ALLOWED_EXTENSIONS = {".txt", ".docx", ".pdf"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

router = APIRouter(tags=["upload"])


@router.post("/contracts/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile) -> ContractUploadResponse:
    original_name = file.filename or "upload"
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{extension or '(none)'}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            ),
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    contract_id = f"upload_{uuid.uuid4().hex[:8]}"
    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)

    # Write to a temp path under the original extension so extraction/parser.py can use
    # its extension-based dispatch, then remove it once we have the plain text.
    temp_path = CONTRACTS_DIR / f"_upload_tmp_{contract_id}{extension}"
    temp_path.write_bytes(contents)
    try:
        # A scanned PDF falls back to OCR here (see extraction/parser.py), which is far
        # slower than direct text extraction - the frontend gives this call extra time
        # to account for that (see UploadContract.jsx), independent of and not affecting
        # the Gemini-call rate-limit/429 handling used elsewhere in the API.
        raw_text, extraction_method = extract_text_from_file(str(temp_path))
    except (UnsupportedFileTypeError, EmptyDocumentError, ScannedDocumentOCRError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    # Fail fast here (rather than on the first extraction call) so the user gets an
    # immediate, specific error if this document isn't actually bilingual.
    try:
        split_bilingual_contract(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    final_path = CONTRACTS_DIR / f"{contract_id}.txt"
    final_path.write_text(raw_text, encoding="utf-8")

    return ContractUploadResponse(
        contract_id=contract_id,
        message=f"Uploaded and processed '{original_name}'.",
        extraction_method=extraction_method,
    )

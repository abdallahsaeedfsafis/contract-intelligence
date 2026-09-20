"""Endpoints for listing contracts and running structured extraction on them."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402

from api import cache  # noqa: E402
from api.errors import to_http_exception  # noqa: E402
from api.schemas import ExtractionResponse  # noqa: E402
from extraction.extractor import extract_contract_data  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"
CACHE_TYPE = "extraction"

router = APIRouter(tags=["extraction"])


@router.get("/contracts")
def list_contracts() -> list[str]:
    # "*.txt" (not "contract_*.txt") so uploaded contracts - which use an "upload_" id
    # prefix, not "contract_" - also show up in the list.
    return sorted(p.stem for p in CONTRACTS_DIR.glob("*.txt"))


@router.post("/contracts/{contract_id}/extract", response_model=ExtractionResponse)
def extract_contract(contract_id: str, force_refresh: bool = False) -> ExtractionResponse:
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    if not contract_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    if not force_refresh:
        cached = cache.get(CACHE_TYPE, contract_id)
        if cached is not None:
            return cached

    contract_text = contract_path.read_text(encoding="utf-8")
    try:
        arabic = extract_contract_data(contract_text, "arabic")
        english = extract_contract_data(contract_text, "english")
    except genai_errors.APIError as exc:
        raise to_http_exception(exc) from exc

    result = ExtractionResponse(contract_id=contract_id, arabic=arabic, english=english)
    cache.set(CACHE_TYPE, contract_id, result)
    return result

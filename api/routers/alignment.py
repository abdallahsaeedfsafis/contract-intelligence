"""Endpoint for cross-lingual discrepancy detection on a contract."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402

from alignment.aligner import analyze_contract  # noqa: E402
from api import cache  # noqa: E402
from api.errors import to_http_exception  # noqa: E402
from api.schemas import AlignmentResponse  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"
CACHE_TYPE = "discrepancies"

router = APIRouter(tags=["alignment"])


@router.get("/contracts/{contract_id}/discrepancies", response_model=AlignmentResponse)
def get_discrepancies(contract_id: str, force_refresh: bool = False) -> AlignmentResponse:
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    if not contract_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    if not force_refresh:
        cached = cache.get(CACHE_TYPE, contract_id)
        if cached is not None:
            return cached

    try:
        report = analyze_contract(contract_id)
    except genai_errors.APIError as exc:
        raise to_http_exception(exc) from exc

    result = AlignmentResponse(**report)
    cache.set(CACHE_TYPE, contract_id, result)
    return result

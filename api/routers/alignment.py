"""Endpoint for cross-lingual discrepancy detection on a contract."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException  # noqa: E402

from alignment.aligner import analyze_contract  # noqa: E402
from api.schemas import AlignmentResponse  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"

router = APIRouter(tags=["alignment"])


@router.get("/contracts/{contract_id}/discrepancies", response_model=AlignmentResponse)
def get_discrepancies(contract_id: str) -> AlignmentResponse:
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    if not contract_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    report = analyze_contract(contract_id)
    return AlignmentResponse(**report)

"""Endpoints for listing contracts and running structured extraction on them."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException  # noqa: E402

from api.schemas import ExtractionResponse  # noqa: E402
from extraction.extractor import extract_contract_data  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"

router = APIRouter(tags=["extraction"])


@router.get("/contracts")
def list_contracts() -> list[str]:
    return sorted(p.stem for p in CONTRACTS_DIR.glob("contract_*.txt"))


@router.post("/contracts/{contract_id}/extract", response_model=ExtractionResponse)
def extract_contract(contract_id: str) -> ExtractionResponse:
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    if not contract_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    contract_text = contract_path.read_text(encoding="utf-8")
    arabic = extract_contract_data(contract_text, "arabic")
    english = extract_contract_data(contract_text, "english")

    return ExtractionResponse(contract_id=contract_id, arabic=arabic, english=english)

"""Endpoint for cross-lingual RAG question-answering on a contract."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, HTTPException  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402

from api.errors import to_http_exception  # noqa: E402
from api.schemas import AnswerResponse, QuestionRequest  # noqa: E402
from rag.qa_engine import answer_question  # noqa: E402
from rag.vector_store import build_contract_index  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"

router = APIRouter(tags=["qa"])


@router.post("/contracts/{contract_id}/ask", response_model=AnswerResponse)
def ask_question(contract_id: str, request: QuestionRequest) -> AnswerResponse:
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    if not contract_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract '{contract_id}' not found.")

    try:
        build_contract_index(contract_id)  # no-op if this contract is already indexed
        result = answer_question(request.query, contract_id)
    except genai_errors.APIError as exc:
        raise to_http_exception(exc) from exc

    return AnswerResponse(**result)

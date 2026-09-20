"""Pydantic request/response models for the contract intelligence API."""

from typing import Any

from pydantic import BaseModel


class ContractUploadResponse(BaseModel):
    contract_id: str
    message: str
    extraction_method: str  # "direct" | "ocr"


class ExtractionResponse(BaseModel):
    contract_id: str
    arabic: dict[str, Any]
    english: dict[str, Any]


class AlignmentResponse(BaseModel):
    contract_id: str
    fields: list[dict[str, Any]]
    discrepancy_count: int
    significant_discrepancy_count: int


class QuestionRequest(BaseModel):
    query: str
    contract_id: str


class AnswerResponse(BaseModel):
    answer: str
    cited_clauses: list[int]
    language_answered_in: str

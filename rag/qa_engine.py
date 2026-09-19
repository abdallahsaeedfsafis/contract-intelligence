"""Cross-lingual contract question-answering: retrieves relevant clauses and answers strictly
from them, in the same language the question was asked in, refusing to guess when the
contract doesn't actually address the question.

Run from the project root: python rag/qa_engine.py
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extraction.extractor import MODEL, _strip_code_fences  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from rag.retriever import retrieve_relevant_clauses  # noqa: E402
from rag.vector_store import build_contract_index  # noqa: E402

_ARABIC_CHAR_RE = re.compile(r"[؀-ۿݐ-ݿ]")

QA_SYSTEM_PROMPT = """You are a contract question-answering assistant. You will be given one or more \
numbered clauses extracted from a bilingual (Arabic/English) contract, and a question about that \
contract. Answer the question using ONLY the information in the clauses provided - never use outside \
knowledge, and never guess or infer information the clauses do not actually state.

Hard requirement: if the provided clauses do not actually answer the question, you MUST respond with \
exactly "Not found in contract." (or, if answering in Arabic, "غير موجود في العقد.") and an empty \
cited_clauses list. This is not a suggestion - do not attempt to guess, approximate, or answer from \
general knowledge. A missing answer is far better than a wrong or invented one.

Answer in {language}, regardless of which language the clause(s) you cite are written in.

Return ONLY a single JSON object with exactly these fields:
- "answer": your answer as a string, in {language}. If unanswerable, exactly "Not found in contract." \
(English) or "غير موجود في العقد." (Arabic), matching the answer language.
- "cited_clauses": an array of the clause numbers (integers) you actually used to answer. Empty array \
if the answer is "not found".

Return raw JSON only: no markdown code fences, no commentary, no explanations outside the JSON object.
"""


def _detect_language(text: str) -> str:
    return "arabic" if _ARABIC_CHAR_RE.search(text) else "english"


def answer_question(query: str, contract_id: str) -> dict:
    """Answer a question about one contract using only its retrieved clauses."""
    language = _detect_language(query)
    language_label = "Arabic" if language == "arabic" else "English"

    clauses = retrieve_relevant_clauses(query, contract_id, top_k=3)
    context = "\n\n".join(f"[Clause {c['clause_number']} ({c['language']})]\n{c['text']}" for c in clauses)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=QA_SYSTEM_PROMPT.format(language=language_label),
        response_mime_type="application/json",
        temperature=0,
    )
    user_message = f"Clauses:\n{context}\n\nQuestion: {query}"

    def _call() -> str:
        response = client.models.generate_content(model=MODEL, contents=user_message, config=config)
        return response.text

    raw = _call()
    try:
        result = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        result = json.loads(_strip_code_fences(_call()))

    return {
        "answer": result.get("answer", "Not found in contract."),
        "cited_clauses": result.get("cited_clauses", []),
        "language_answered_in": language,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not found. Set it in .env or your environment.")

    contract_id = "contract_01"
    indexed = build_contract_index(contract_id)
    print(f"{contract_id}: {'indexed ' + str(indexed) + ' clauses' if indexed else 'already indexed, skipped'}")
    print()

    test_cases = [
        ("ما هو الراتب الشهري للموظف؟", "Arabic question, answerable from the contract"),
        ("What is the notice period required to terminate this contract?", "English question, answerable from the contract"),
        ("What is the penalty for late delivery of goods under this contract?", "Question NOT covered by this contract (guardrail test)"),
    ]

    for query, label in test_cases:
        print("=" * 80)
        print(label)
        print("=" * 80)
        print(f"Q: {query}")
        result = answer_question(query, contract_id)
        print(f"A ({result['language_answered_in']}): {result['answer']}")
        print(f"Cited clauses: {result['cited_clauses']}")
        print()

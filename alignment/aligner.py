"""Cross-lingual clause alignment and contradiction detection for bilingual contracts.

For each schema field extracted from a contract's Arabic and English sections, judges
whether the two values express the same substantive meaning or a real discrepancy.

Run from the project root: python alignment/aligner.py
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extraction.extractor import (  # noqa: E402
    MODEL,
    SCHEMA_PATH,
    _strip_code_fences,
    extract_contract_data,
)
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
CALL_DELAY_SECONDS = 1  # be gentle on free-tier rate limits

EQUIVALENCE_SYSTEM_PROMPT = """You are a bilingual (Arabic/English) contract-review assistant. You \
will be given ONE field extracted from the same contract's Arabic section and English section. \
Decide whether the two values express the SAME substantive meaning.

Distinguish:
- "Different wording, same meaning": different date formats, "30 days" vs "thirty (30) days", a more \
verbose vs terser phrasing of the identical clause, ordinary translation variance. Judge these as a match.
- "Different substance": different amounts, different currencies, different deadlines/durations, \
different obligations or conditions, or one side stating something material the other omits entirely. \
Judge these as a discrepancy.

Return ONLY a single JSON object with exactly these fields:
- "status": one of "match" (same substance), "discrepancy" (different substance), or "uncertain" \
(cannot confidently determine from the given values - e.g. both sides are empty, or too vague to compare).
- "explanation": a short, one-sentence reason for your judgment, in English.
- "severity": one of "none", "minor", or "significant".
  - "none": used only when status is "match".
  - "minor": a discrepancy that is stylistic or trivial and unlikely to matter legally or financially.
  - "significant": a discrepancy that could have real legal or financial consequences - e.g. different \
amounts, different deadlines, different obligations, different termination conditions.

Return raw JSON only: no markdown code fences, no commentary, no explanations outside the JSON object.
"""


def _with_retry(fn, *args, **kwargs):
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - any API/parse failure should retry, not crash the run
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(str(last_error)) from last_error


def _schema_field_names() -> list:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return list(json.load(f)["fields"].keys())


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return all(_is_empty(v) for v in value.values())
    return False


def align_clauses(extracted_arabic: dict, extracted_english: dict) -> list:
    """Pair up the Arabic and English extracted values for every field defined in the schema."""
    return [
        {
            "field_name": field_name,
            "arabic_value": extracted_arabic.get(field_name),
            "english_value": extracted_english.get(field_name),
        }
        for field_name in _schema_field_names()
    ]


def check_equivalence(field_name: str, arabic_value, english_value) -> dict:
    """Judge whether an Arabic/English field pair express the same substantive meaning via Gemini."""
    if _is_empty(arabic_value) and _is_empty(english_value):
        return {"status": "match", "explanation": "Field not present in either language version.", "severity": "none"}

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=EQUIVALENCE_SYSTEM_PROMPT,
        response_mime_type="application/json",
    )
    user_message = (
        f'Field: "{field_name}"\n'
        f"Arabic value: {json.dumps(arabic_value, ensure_ascii=False)}\n"
        f"English value: {json.dumps(english_value, ensure_ascii=False)}"
    )

    def _call() -> str:
        response = client.models.generate_content(model=MODEL, contents=user_message, config=config)
        return response.text

    raw = _call()
    try:
        result = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        result = json.loads(_strip_code_fences(_call()))

    return {
        "status": result.get("status", "uncertain"),
        "explanation": result.get("explanation", ""),
        "severity": result.get("severity", "none"),
    }


def analyze_contract(contract_id: str) -> dict:
    """Extract both language sections of a contract and check every field for cross-lingual discrepancies."""
    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    contract_text = contract_path.read_text(encoding="utf-8")

    arabic_extracted = _with_retry(extract_contract_data, contract_text, "arabic")
    time.sleep(CALL_DELAY_SECONDS)
    english_extracted = _with_retry(extract_contract_data, contract_text, "english")
    time.sleep(CALL_DELAY_SECONDS)

    pairs = align_clauses(arabic_extracted, english_extracted)

    fields = []
    for pair in pairs:
        equivalence = _with_retry(check_equivalence, pair["field_name"], pair["arabic_value"], pair["english_value"])
        fields.append({**pair, **equivalence})
        time.sleep(CALL_DELAY_SECONDS)

    discrepancy_count = sum(1 for f in fields if f["status"] == "discrepancy")
    significant_discrepancy_count = sum(
        1 for f in fields if f["status"] == "discrepancy" and f["severity"] == "significant"
    )

    return {
        "contract_id": contract_id,
        "fields": fields,
        "discrepancy_count": discrepancy_count,
        "significant_discrepancy_count": significant_discrepancy_count,
    }


def _print_report(report: dict) -> None:
    print("=" * 80)
    print(f"CONTRACT: {report['contract_id']}".center(80))
    print("=" * 80)
    for f in report["fields"]:
        print(f"\n[{f['field_name']}]  status={f['status']}  severity={f['severity']}")
        print(f"  Arabic:  {json.dumps(f['arabic_value'], ensure_ascii=False)}")
        print(f"  English: {json.dumps(f['english_value'], ensure_ascii=False)}")
        print(f"  Explanation: {f['explanation']}")
    print(
        f"\nDiscrepancies: {report['discrepancy_count']}"
        f"  (significant: {report['significant_discrepancy_count']})"
    )
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not found. Set it in .env or your environment.")

    for contract_id in ("contract_01", "contract_06"):
        report = analyze_contract(contract_id)
        _print_report(report)

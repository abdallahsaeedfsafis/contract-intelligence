"""Structured extraction of contract fields from bilingual (Arabic/English) contract text.

Currently using Gemini API as a free alternative; swap to Anthropic API (see commented
reference below) once Anthropic credits are available.
"""

import json
import os
from pathlib import Path

from google import genai
from google.genai import types

# --- Anthropic reference (swap back in once credits are available) ---------------
# import anthropic
#
# MODEL = "claude-sonnet-4-5"
#
# def extract_contract_data(contract_text: str, language: str) -> dict:
#     sections = split_bilingual_contract(contract_text)
#     section_text = sections[language]
#     client = anthropic.Anthropic()
#     system_prompt = _build_system_prompt()
#
#     def _call() -> str:
#         response = client.messages.create(
#             model=MODEL,
#             max_tokens=2048,
#             system=system_prompt,
#             messages=[{"role": "user", "content": section_text}],
#         )
#         return response.content[0].text
#
#     raw = _call()
#     try:
#         return json.loads(_strip_code_fences(raw))
#     except json.JSONDecodeError:
#         return json.loads(_strip_code_fences(_call()))
# -----------------------------------------------------------------------------------

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "schema.json"
# "gemini-2.5-flash" returns 404 for this API key (Google reports it is no longer
# available to new users, and "-flash-lite"/"-pro"/"-latest" variants either share
# that deprecation or were overloaded with 503s at time of writing). This lite model
# was confirmed reachable for this key; swap freely as availability changes.
MODEL = "gemini-3.1-flash-lite"

ARABIC_HEADER = "النسخة العربية"
ENGLISH_HEADER = "English Version"


def split_bilingual_contract(text: str) -> dict:
    """Split a contract's raw text into its Arabic and English sections."""
    ar_idx = text.find(ARABIC_HEADER)
    en_idx = text.find(ENGLISH_HEADER)
    if ar_idx == -1 or en_idx == -1:
        raise ValueError(
            f"Could not find both section headers ('{ARABIC_HEADER}' and '{ENGLISH_HEADER}') in the contract text."
        )

    if ar_idx < en_idx:
        arabic_start = text.find("\n", ar_idx) + 1
        arabic_text = text[arabic_start:en_idx]
        english_start = text.find("\n", en_idx) + 1
        english_text = text[english_start:]
    else:
        english_start = text.find("\n", en_idx) + 1
        english_text = text[english_start:ar_idx]
        arabic_start = text.find("\n", ar_idx) + 1
        arabic_text = text[arabic_start:]

    def _is_blank_or_rule(line: str) -> bool:
        stripped = line.strip()
        return stripped == "" or set(stripped) == {"="}

    def _clean(section: str) -> str:
        lines = section.split("\n")
        while lines and _is_blank_or_rule(lines[0]):
            lines.pop(0)
        while lines and _is_blank_or_rule(lines[-1]):
            lines.pop()
        return "\n".join(lines).strip()

    return {"arabic": _clean(arabic_text), "english": _clean(english_text)}


def _load_schema_fields() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)["fields"]


def _build_system_prompt() -> str:
    fields = _load_schema_fields()
    field_lines = []
    for name, spec in fields.items():
        example = json.dumps(spec["example"], ensure_ascii=False)
        field_lines.append(f'- "{name}" ({spec["type"]}): {spec["description"]} Example: {example}')

    return (
        "You are a contract data extraction system. Extract structured information from the "
        "contract text provided by the user and return ONLY a single JSON object with exactly "
        "the following fields, matching the types and shapes shown:\n\n"
        + "\n".join(field_lines)
        + "\n\nRules:\n"
        "- Extract values only from the text provided; never invent information.\n"
        "- If a field is not present or cannot be determined from the text, use null "
        "(or an empty array for array fields).\n"
        "- Stay strictly literal when paraphrasing free-text fields (payment_terms, governing_law, "
        "termination_clauses, penalty_clauses, language_precedence_clause, duration). Do not add "
        "descriptive qualifiers, scope words, or interpretive detail that is not explicitly stated - "
        "e.g. if the source says a jurisdiction \"has\" jurisdiction, do not write \"exclusive\" "
        "jurisdiction unless the source itself says so; if the source says a penalty applies to a "
        "breach of \"obligations\", do not narrow that to \"confidentiality obligations\" unless the "
        "source itself says so. When in doubt, paraphrase closer to the source wording rather than "
        "adding clarifying detail a human reader might infer from context.\n"
        "- financial_value: capture ANY monetary figure stated anywhere in the contract, not just "
        "a recurring salary or rent. This includes one-time amounts such as penalties, liquidated "
        "damages, or security deposits - e.g. an NDA with no recurring payment but a liquidated "
        "damages clause of USD 50,000 should report amount: 50000, currency: \"USD\". Only use "
        "null for amount and currency if the contract mentions no monetary figure of any kind.\n"
        "- List fields (parties, termination_clauses, penalty_clauses): return an empty array only "
        "if the contract truly does not address that category at all. If the contract contains any "
        "relevant sentence on the topic - even a statement that no penalty applies, or that the "
        "matter is governed by statute rather than a contract-specific clause - extract that "
        "sentence as one list item rather than returning an empty array.\n"
        "- duration: extract every relevant sub-detail mentioned, not just the base term - include "
        "any probationary period, notice period, or renewal/auto-renewal terms stated alongside it.\n"
        "- Return raw JSON only: no markdown code fences, no commentary, no explanations.\n"
    )


def _strip_code_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def extract_contract_data(contract_text: str, language: str) -> dict:
    """Extract schema fields from one language section of a contract via the Gemini API."""
    if language not in ("arabic", "english"):
        raise ValueError('language must be "arabic" or "english"')

    sections = split_bilingual_contract(contract_text)
    section_text = sections[language]

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    system_prompt = _build_system_prompt()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        # Deterministic output reduces wording variance between runs and between the
        # Arabic/English extractions of the same underlying fact, which otherwise shows
        # up downstream as spurious cross-lingual "discrepancies" (see alignment/aligner.py).
        temperature=0,
    )

    def _call() -> str:
        response = client.models.generate_content(
            model=MODEL,
            contents=section_text,
            config=config,
        )
        return response.text

    raw = _call()
    try:
        return json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        raw_retry = _call()
        return json.loads(_strip_code_fences(raw_retry))


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not found. Set it in .env or your environment.")

    contract_path = Path(__file__).resolve().parent.parent / "data" / "raw_contracts" / "contract_01.txt"
    contract_text = contract_path.read_text(encoding="utf-8")

    arabic_result = extract_contract_data(contract_text, "arabic")
    english_result = extract_contract_data(contract_text, "english")

    print("=" * 80)
    print("ARABIC EXTRACTION".center(80))
    print("=" * 80)
    print(json.dumps(arabic_result, ensure_ascii=False, indent=2))

    print()
    print("=" * 80)
    print("ENGLISH EXTRACTION".center(80))
    print("=" * 80)
    print(json.dumps(english_result, ensure_ascii=False, indent=2))

    print()
    print("=" * 80)
    print("SIDE-BY-SIDE FIELD COMPARISON".center(80))
    print("=" * 80)
    all_fields = sorted(set(arabic_result) | set(english_result))
    for field in all_fields:
        print(f"\n[{field}]")
        print(f"  Arabic:  {json.dumps(arabic_result.get(field), ensure_ascii=False)}")
        print(f"  English: {json.dumps(english_result.get(field), ensure_ascii=False)}")

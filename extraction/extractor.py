"""Structured extraction of contract fields from bilingual (Arabic/English) contract text.

Currently using Gemini API as a free alternative; swap to Anthropic API (see commented
reference below) once Anthropic credits are available.
"""

import json
import os
import re
from pathlib import Path

import langdetect
from google import genai
from google.genai import types
from langdetect.lang_detect_exception import LangDetectException

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

# Number of consecutive paragraphs of the "other" language required before we treat a
# language change as a real section boundary, rather than a single stray sentence.
AUTO_SPLIT_SUSTAINED_RUN = 2

langdetect.DetectorFactory.seed = 0  # deterministic detection
_ARABIC_CHAR_RE = re.compile(r"[؀-ۿݐ-ݿ]")

# Maps common Arabic/English currency names to their ISO 4217 code. Keys are matched as
# case-insensitive substrings against the extracted currency value, longest-first, so a
# more specific phrase (e.g. "Qatari Riyal") is checked before a shorter one that could
# otherwise false-match inside it.
CURRENCY_ALIASES = {
    "AED": "AED",
    "SAR": "SAR",
    "QAR": "QAR",
    "EGP": "EGP",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "UAE Dirhams": "AED",
    "UAE Dirham": "AED",
    "Emirati Dirhams": "AED",
    "Emirati Dirham": "AED",
    "Saudi Riyals": "SAR",
    "Saudi Riyal": "SAR",
    "Saudi Arabian Riyal": "SAR",
    "Qatari Riyals": "QAR",
    "Qatari Riyal": "QAR",
    "Egyptian Pounds": "EGP",
    "Egyptian Pound": "EGP",
    "United States Dollars": "USD",
    "United States Dollar": "USD",
    "US Dollars": "USD",
    "US Dollar": "USD",
    "American Dollars": "USD",
    "American Dollar": "USD",
    "Euros": "EUR",
    "Euro": "EUR",
    "British Pounds": "GBP",
    "British Pound": "GBP",
    "Pounds Sterling": "GBP",
    "Pound Sterling": "GBP",
    "الدرهم الإماراتي": "AED",
    "دراهم إماراتية": "AED",
    "درهم إماراتي": "AED",
    "الريال السعودي": "SAR",
    "ريالات سعودية": "SAR",
    "ريال سعودي": "SAR",
    "الريال القطري": "QAR",
    "ريالات قطرية": "QAR",
    "ريال قطري": "QAR",
    "الجنيه المصري": "EGP",
    "جنيهات مصرية": "EGP",
    "جنيه مصري": "EGP",
    "الدولار الأمريكي": "USD",
    "دولارات أمريكية": "USD",
    "دولار أمريكي": "USD",
    "دولار امريكي": "USD",
    "اليورو": "EUR",
    "يورو": "EUR",
    "الجنيه الإسترليني": "GBP",
    "جنيه إسترليني": "GBP",
    "جنيه استرليني": "GBP",
}


def normalize_currency(value: str) -> str:
    """Map a currency name/phrase (Arabic or English) to its ISO 4217 code.

    Leaves the value unchanged if it doesn't match any known alias, rather than guessing.
    """
    if not value or not isinstance(value, str):
        return value

    normalized = " ".join(value.strip().split()).lower()
    for alias, code in sorted(CURRENCY_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if alias.lower() in normalized:
            return code
    return value


def _detect_paragraph_language(paragraph: str) -> str | None:
    """Return "arabic", "english", or None (paragraph too short/ambiguous to classify)."""
    stripped = paragraph.strip()
    if not stripped:
        return None
    try:
        detected = langdetect.detect(stripped)
    except LangDetectException:
        detected = None
    if detected == "ar":
        return "arabic"
    if detected == "en":
        return "english"
    # langdetect struggles on short paragraphs (headings, dates, numbers); fall back to a
    # simple script check rather than leaving them unclassified.
    return "arabic" if _ARABIC_CHAR_RE.search(stripped) else "english"


def _auto_split_bilingual(text: str) -> dict:
    """Best-effort split for contracts that don't use the standard section headers:
    scan paragraph by paragraph and split where the dominant language changes for a
    sustained run of paragraphs, rather than on a single stray sentence."""
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    labels = [_detect_paragraph_language(p) for p in paragraphs]

    split_index = None
    for i in range(1, len(labels)):
        prior_labels = [label for label in labels[:i] if label]
        if not prior_labels:
            continue
        window = [label for label in labels[i : i + AUTO_SPLIT_SUSTAINED_RUN] if label]
        if len(window) < AUTO_SPLIT_SUSTAINED_RUN:
            continue
        new_language = window[0]
        if new_language != prior_labels[-1] and all(label == new_language for label in window):
            split_index = i
            break

    error = ValueError(
        "Could not automatically detect a bilingual Arabic/English split in this document. "
        "Please confirm it actually contains both an Arabic section and an English section."
    )
    if split_index is None:
        raise error

    first_block = "\n\n".join(paragraphs[:split_index]).strip()
    second_block = "\n\n".join(paragraphs[split_index:]).strip()
    first_language = next((label for label in labels[:split_index] if label), None)
    second_language = next((label for label in labels[split_index:] if label), None)

    if first_language == "arabic" and second_language == "english":
        return {"arabic": first_block, "english": second_block}
    if first_language == "english" and second_language == "arabic":
        return {"arabic": second_block, "english": first_block}
    raise error


def split_bilingual_contract(text: str) -> dict:
    """Split a contract's raw text into its Arabic and English sections.

    Looks for the standard "النسخة العربية" / "English Version" headers first; if a
    contract (e.g. a user upload) doesn't use them, falls back to auto-detecting the
    split via per-paragraph language detection (see _auto_split_bilingual).
    """
    ar_idx = text.find(ARABIC_HEADER)
    en_idx = text.find(ENGLISH_HEADER)
    if ar_idx == -1 or en_idx == -1:
        return _auto_split_bilingual(text)

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
        result = json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        raw_retry = _call()
        result = json.loads(_strip_code_fences(raw_retry))

    financial_value = result.get("financial_value")
    if isinstance(financial_value, dict) and financial_value.get("currency"):
        financial_value["currency"] = normalize_currency(financial_value["currency"])

    return result


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

"""Evaluate contract extraction accuracy across all synthetic contracts against ground truth labels.

Run from the project root: python eval/extraction_eval.py
"""

import difflib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extraction.extractor import extract_contract_data, MODEL as MODEL_NAME  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"
GROUND_TRUTH_DIR = ROOT / "data" / "ground_truth"
REPORT_PATH = Path(__file__).resolve().parent / "extraction_eval_report.json"

LANGUAGES = ("arabic", "english")

SIMPLE_FIELDS = [
    "effective_date",
    "financial_value.amount",
    "financial_value.currency",
    "governing_law",
    "language_precedence_clause",
]
LIST_FIELDS = ["parties", "termination_clauses", "penalty_clauses"]

# Prose fields (governing_law, language_precedence_clause) tolerate more paraphrase
# than short structured fields (dates, currency codes), hence two thresholds.
NEAR_EXACT_THRESHOLD = 0.85
PROSE_THRESHOLD = 0.6

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
CALL_DELAY_SECONDS = 1  # be gentle on free-tier rate limits

_ARABIC_CHAR_RE = re.compile(r"[؀-ۿݐ-ݿ]")
_PREVAIL_PATTERNS = (
    (re.compile(r"تسود\s+النسخة\s+العربية"), "arabic"),
    (re.compile(r"تسود\s+النسخة\s+الإنجليزية"), "english"),
    (re.compile(r"\bArabic\s+version\s+shall\s+prevail\b", re.IGNORECASE), "arabic"),
    (re.compile(r"\bEnglish\s+version\s+shall\s+prevail\b", re.IGNORECASE), "english"),
)


def _contains_arabic(text) -> bool:
    return bool(text) and bool(_ARABIC_CHAR_RE.search(str(text)))


def _prevailing_language(text) -> str | None:
    """Pull out which language a precedence clause names as controlling, regardless
    of source language or exact phrasing - e.g. both "In case of conflict, the Arabic
    version shall prevail." and "تسود النسخة العربية..." resolve to "arabic". This is
    what the field actually means to convey, so it is a far more meaningful comparison
    than raw text similarity for this specific field."""
    if not text:
        return None
    for pattern, label in _PREVAIL_PATTERNS:
        if pattern.search(str(text)):
            return label
    return None


def _get_field(data: dict, dotted_field: str):
    value = data
    for part in dotted_field.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _field_group(field: str) -> str:
    return field.split(".")[0]


def _text_similarity(a, b) -> float:
    return difflib.SequenceMatcher(None, str(a).strip().lower(), str(b).strip().lower()).ratio()


def _evaluate_simple_field(field: str, extracted_value, truth_value) -> str:
    """Return "match", "mismatch", or "not_comparable" (excluded from accuracy scoring)."""
    if extracted_value is None and truth_value is None:
        return "match"
    if extracted_value is None or truth_value is None:
        return "mismatch"

    if field == "financial_value.amount":
        try:
            return "match" if abs(float(extracted_value) - float(truth_value)) < 0.01 else "mismatch"
        except (TypeError, ValueError):
            similar = _text_similarity(extracted_value, truth_value) >= NEAR_EXACT_THRESHOLD
            return "match" if similar else "mismatch"

    if field == "language_precedence_clause":
        # Compare *which language prevails*, not exact wording - see _prevailing_language().
        extracted_label = _prevailing_language(extracted_value)
        truth_label = _prevailing_language(truth_value)
        if extracted_label is not None and truth_label is not None:
            return "match" if extracted_label == truth_label else "mismatch"
        # Fall back to text similarity if the clause couldn't be parsed into a label.
        similar = _text_similarity(extracted_value, truth_value) >= PROSE_THRESHOLD
        return "match" if similar else "mismatch"

    if field == "governing_law" and _contains_arabic(extracted_value) != _contains_arabic(truth_value):
        # Ground truth is English-only; an Arabic-script extraction can't be fairly
        # scored against it with plain text similarity without a translation step.
        # True cross-lingual comparison belongs to the multilingual-embedding
        # alignment component (see CLAUDE.md Phase 3), not this eval script.
        return "not_comparable"

    threshold = PROSE_THRESHOLD if field == "governing_law" else NEAR_EXACT_THRESHOLD
    similar = _text_similarity(extracted_value, truth_value) >= threshold
    return "match" if similar else "mismatch"


def _list_field_check(extracted_value, truth_value) -> dict:
    extracted_list = extracted_value if isinstance(extracted_value, list) else []
    truth_list = truth_value if isinstance(truth_value, list) else []
    return {
        "expected_count": len(truth_list),
        "extracted_count": len(extracted_list),
        "count_match": len(extracted_list) == len(truth_list),
        "missing_items": max(0, len(truth_list) - len(extracted_list)),
    }


def _extract_with_retry(contract_text: str, language: str) -> dict:
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return extract_contract_data(contract_text, language)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any API/parse failure should retry, not crash the run
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError(str(last_error)) from last_error


def _load_discrepancy_exclusions() -> set:
    """(contract_id, field_group) pairs to exclude from accuracy scoring.

    These are contracts where the Arabic and English text were *deliberately* made to
    differ (see data/ground_truth/discrepancies.json). A per-language extraction that
    faithfully reports its own section's wording will legitimately disagree with the
    single ground-truth value (which reflects whichever language prevails), and that
    disagreement belongs to the contradiction-detection eval, not extraction accuracy.
    """
    path = GROUND_TRUTH_DIR / "discrepancies.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {(d["contract_id"], d["field"]) for d in data["discrepancies"]}


def evaluate() -> dict:
    exclusions = _load_discrepancy_exclusions()
    contract_files = sorted(CONTRACTS_DIR.glob("contract_*.txt"))

    stats = {lang: {field: {"correct": 0, "total": 0} for field in SIMPLE_FIELDS + LIST_FIELDS} for lang in LANGUAGES}
    issues = []
    failures = []
    excluded = []
    not_comparable = []

    for contract_path in contract_files:
        contract_id = contract_path.stem
        truth_path = GROUND_TRUTH_DIR / f"{contract_id}_truth.json"
        if not truth_path.exists():
            issues.append(
                {"contract_id": contract_id, "language": None, "field": None, "issue": f"No ground truth file found ({truth_path.name})"}
            )
            continue

        contract_text = contract_path.read_text(encoding="utf-8")
        with open(truth_path, encoding="utf-8") as f:
            truth = json.load(f)

        for language in LANGUAGES:
            try:
                extracted = _extract_with_retry(contract_text, language)
            except Exception as exc:  # noqa: BLE001
                failures.append({"contract_id": contract_id, "language": language, "error": str(exc)})
                print(f"  [SKIP] {contract_id} ({language}): failed after {MAX_ATTEMPTS} attempts - {exc}")
                continue
            finally:
                time.sleep(CALL_DELAY_SECONDS)

            for field in SIMPLE_FIELDS:
                if (contract_id, _field_group(field)) in exclusions:
                    excluded.append({"contract_id": contract_id, "language": language, "field": field})
                    continue
                extracted_value = _get_field(extracted, field)
                truth_value = _get_field(truth, field)
                status = _evaluate_simple_field(field, extracted_value, truth_value)
                if status == "not_comparable":
                    not_comparable.append(
                        {
                            "contract_id": contract_id,
                            "language": language,
                            "field": field,
                            "reason": "cross-lingual comparison: extracted value is in a different script than the (English-only) ground truth",
                            "extracted": extracted_value,
                            "expected": truth_value,
                        }
                    )
                    continue
                stats[language][field]["total"] += 1
                if status == "match":
                    stats[language][field]["correct"] += 1
                else:
                    issues.append(
                        {
                            "contract_id": contract_id,
                            "language": language,
                            "field": field,
                            "issue": "value mismatch",
                            "extracted": extracted_value,
                            "expected": truth_value,
                        }
                    )

            for field in LIST_FIELDS:
                if (contract_id, field) in exclusions:
                    excluded.append({"contract_id": contract_id, "language": language, "field": field})
                    continue
                extracted_value = _get_field(extracted, field)
                truth_value = _get_field(truth, field)
                result = _list_field_check(extracted_value, truth_value)
                stats[language][field]["total"] += 1
                if result["count_match"]:
                    stats[language][field]["correct"] += 1
                else:
                    issues.append(
                        {
                            "contract_id": contract_id,
                            "language": language,
                            "field": field,
                            "issue": (
                                f"incomplete extraction: expected {result['expected_count']} item(s), "
                                f"got {result['extracted_count']} (missing {result['missing_items']})"
                            ),
                            "extracted_count": result["extracted_count"],
                            "expected_count": result["expected_count"],
                        }
                    )

        print(f"  Processed {contract_id}")

    field_accuracy = {}
    for language in LANGUAGES:
        field_accuracy[language] = {}
        for field, counts in stats[language].items():
            total = counts["total"]
            pct = round(100 * counts["correct"] / total, 1) if total else None
            field_accuracy[language][field] = {"correct": counts["correct"], "total": total, "accuracy_pct": pct}

    overall_accuracy_pct = {}
    for language in LANGUAGES:
        total_correct = sum(v["correct"] for v in field_accuracy[language].values())
        total_count = sum(v["total"] for v in field_accuracy[language].values())
        overall_accuracy_pct[language] = round(100 * total_correct / total_count, 1) if total_count else None

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": MODEL_NAME,
        "contracts_found": len(contract_files),
        "contracts_failed": failures,
        "field_accuracy": field_accuracy,
        "overall_accuracy_pct": overall_accuracy_pct,
        "extraction_issues": issues,
        "excluded_known_discrepancies": excluded,
        "cross_lingual_not_comparable": not_comparable,
    }


def print_summary(report: dict) -> None:
    print("\n" + "=" * 80)
    print("EXTRACTION ACCURACY SUMMARY".center(80))
    print("=" * 80)
    print(f"Model: {report['model']}  |  Contracts found: {report['contracts_found']}")

    for language in LANGUAGES:
        print(f"\n--- {language.upper()} (overall: {report['overall_accuracy_pct'][language]}%) ---")
        for field, v in report["field_accuracy"][language].items():
            print(f"  {field:<32} {v['correct']:>2}/{v['total']:<2}  ({v['accuracy_pct']}%)")

    if report["contracts_failed"]:
        print(f"\n--- SKIPPED (API failures after {MAX_ATTEMPTS} attempts) ---")
        for f in report["contracts_failed"]:
            print(f"  {f['contract_id']} ({f['language']}): {f['error']}")

    if report["extraction_issues"]:
        print(f"\n--- EXTRACTION ISSUES ({len(report['extraction_issues'])}) ---")
        for issue in report["extraction_issues"]:
            print(f"  {issue['contract_id']} [{issue['language']}] {issue['field']}: {issue['issue']}")
    else:
        print("\nNo extraction issues found.")

    if report["excluded_known_discrepancies"]:
        print(
            f"\n({len(report['excluded_known_discrepancies'])} field checks excluded from scoring - "
            "known Arabic/English discrepancies, see data/ground_truth/discrepancies.json)"
        )

    if report["cross_lingual_not_comparable"]:
        print(
            f"\n({len(report['cross_lingual_not_comparable'])} field checks excluded from scoring - "
            "extracted value's script doesn't match the English-only ground truth; see "
            "cross_lingual_not_comparable in the report for details)"
        )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print(f"Evaluating extraction across contracts in {CONTRACTS_DIR} ...")
    report = evaluate()

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print_summary(report)
    print(f"\nFull report saved to {REPORT_PATH}")

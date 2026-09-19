"""Translates Gemini API errors into clean HTTP responses, with special handling for
rate limits so the frontend can show a friendly wait message instead of a raw failure.
"""

import re

from fastapi import HTTPException
from google.genai import errors as genai_errors

_RETRY_DELAY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s")
DEFAULT_RETRY_AFTER_SECONDS = 30


def _extract_retry_after_seconds(exc: genai_errors.APIError) -> int:
    """Best-effort parse of the API's suggested retry delay (falls back to a fixed default;
    the exact shape of Gemini's RetryInfo detail wasn't verified against a live 429)."""
    try:
        details = exc.details
        if isinstance(details, dict) and "error" in details:
            details = details["error"]
        for detail in (details or {}).get("details", []):
            if str(detail.get("@type", "")).endswith("RetryInfo"):
                match = _RETRY_DELAY_RE.search(str(detail.get("retryDelay", "")))
                if match:
                    return max(1, round(float(match.group(1))))
    except Exception:  # noqa: BLE001 - parsing is best-effort, never let it break error handling
        pass
    return DEFAULT_RETRY_AFTER_SECONDS


def to_http_exception(exc: Exception) -> HTTPException:
    """Convert a Gemini API error into an HTTPException - 429 with Retry-After for rate
    limits, 502 for any other upstream model failure (e.g. transient 503 overload)."""
    if isinstance(exc, genai_errors.ClientError) and exc.code == 429:
        retry_after = _extract_retry_after_seconds(exc)
        return HTTPException(
            status_code=429,
            detail={
                "message": f"Rate limit reached, please wait {retry_after} seconds and try again.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
    return HTTPException(status_code=502, detail=f"Upstream model call failed: {exc}")

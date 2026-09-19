"""Simple in-process cache for extraction/alignment results.

Avoids redundant Gemini API calls when the frontend switches tabs and re-requests the
same contract's data. Lives only for the current server process - cleared on restart,
never persisted, and shared across all clients hitting this server instance.
"""

_store: dict[tuple[str, str], object] = {}


def get(cache_type: str, contract_id: str):
    return _store.get((cache_type, contract_id))


def set(cache_type: str, contract_id: str, value) -> None:
    _store[(cache_type, contract_id)] = value


def clear(cache_type: str, contract_id: str) -> None:
    _store.pop((cache_type, contract_id), None)

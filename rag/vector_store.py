"""Builds a cross-lingual clause-level vector index for contracts using Gemini embeddings + ChromaDB.

Clauses from both the Arabic and English sections of a contract are embedded into the same
vector space and stored in one shared ChromaDB collection, filterable by contract_id, so
retrieval can match a question to its most relevant clause regardless of language.
"""

import os
import re
import sys
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from extraction.extractor import split_bilingual_contract  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

CONTRACTS_DIR = ROOT / "data" / "raw_contracts"
CHROMA_DB_DIR = ROOT / "chroma_db"
COLLECTION_NAME = "contract_clauses"
EMBEDDING_MODEL = "models/gemini-embedding-001"

# Splits each language section right before an "Article N" / "المادة N" marker, so the
# marker stays attached to the start of the clause it introduces.
_CLAUSE_SPLIT_RE = re.compile(r"(?=(?:Article|المادة)\s+\d+)")
_CLAUSE_NUMBER_RE = re.compile(r"(?:Article|المادة)\s+(\d+)")


def _split_into_clauses(section_text: str) -> list:
    """Split one language section into individual numbered clauses.

    Any text before the first "Article"/"المادة" marker (title, parties, preamble) is kept
    as clause 0, since it can still hold answerable information (e.g. who the parties are).
    """
    chunks = [c.strip() for c in _CLAUSE_SPLIT_RE.split(section_text) if c.strip()]
    clauses = []
    for chunk in chunks:
        match = _CLAUSE_NUMBER_RE.match(chunk)
        clause_number = int(match.group(1)) if match else 0
        clauses.append({"clause_number": clause_number, "text": chunk})
    return clauses


def _embed(text: str, task_type: str) -> list:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.EmbedContentConfig(task_type=task_type)
    response = client.models.embed_content(model=EMBEDDING_MODEL, contents=text, config=config)
    return list(response.embeddings[0].values)


def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def build_contract_index(contract_id: str, force: bool = False) -> int:
    """Embed and store every clause of a contract's Arabic and English sections.

    Returns the number of clauses indexed. If the contract is already indexed and
    force=False, does nothing and returns 0.

    Idempotent and safe to call unconditionally before every question (see
    rag/qa_engine.py's caller) rather than assuming indexing already happened once and
    persisted - on a host with ephemeral storage (e.g. Render's free tier), chroma_db/ is
    wiped on every restart/redeploy, so "already indexed" is only ever true within a
    single running container's lifetime. The first question about a contract after a
    fresh start just rebuilds its index on demand; verified this works from a totally
    empty chroma_db/ with no prior state.
    """
    collection = _get_collection()

    if not force:
        existing = collection.get(where={"contract_id": contract_id}, limit=1)
        if existing["ids"]:
            return 0
    else:
        collection.delete(where={"contract_id": contract_id})

    contract_path = CONTRACTS_DIR / f"{contract_id}.txt"
    contract_text = contract_path.read_text(encoding="utf-8")
    sections = split_bilingual_contract(contract_text)

    ids, embeddings, documents, metadatas = [], [], [], []
    for language, section_text in sections.items():
        for clause in _split_into_clauses(section_text):
            ids.append(f"{contract_id}_{language}_{clause['clause_number']}")
            embeddings.append(_embed(clause["text"], task_type="RETRIEVAL_DOCUMENT"))
            documents.append(clause["text"])
            metadatas.append(
                {
                    "contract_id": contract_id,
                    "language": language,
                    "clause_number": clause["clause_number"],
                }
            )

    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    return len(ids)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY not found. Set it in .env or your environment.")

    for path in sorted(CONTRACTS_DIR.glob("contract_*.txt")):
        count = build_contract_index(path.stem)
        status = f"indexed {count} clauses" if count else "already indexed, skipped"
        print(f"{path.stem}: {status}")

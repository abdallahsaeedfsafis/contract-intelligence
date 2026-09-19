"""Cross-lingual clause retrieval: finds the most relevant clauses for a question regardless
of whether the question or the clause is in Arabic or English, since both are embedded into
the same vector space (see rag/vector_store.py).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rag.vector_store import _embed, _get_collection  # noqa: E402


def retrieve_relevant_clauses(query: str, contract_id: str, top_k: int = 3) -> list:
    """Return the top_k clauses (any language) most relevant to query, for one contract."""
    collection = _get_collection()
    query_vector = _embed(query, task_type="RETRIEVAL_QUERY")

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        where={"contract_id": contract_id},
    )

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        {
            "clause_id": ids[i],
            "text": documents[i],
            "language": metadatas[i]["language"],
            "clause_number": metadatas[i]["clause_number"],
            "distance": distances[i],
        }
        for i in range(len(ids))
    ]

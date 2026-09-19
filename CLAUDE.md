# Bilingual Contract Intelligence System

## Project Overview

An AI system that analyzes bilingual (Arabic/English) contracts by:
1. Extracting key clauses in a structured format
2. Aligning clauses between the Arabic and English versions and detecting contradictions between them
3. Answering questions about the contract (RAG) in either language
4. Displaying results through a FastAPI backend with a React frontend

**Problem it solves:** Existing contract-analysis tools (Ironclad, Luminance, etc.) are built primarily
for English. Bilingual contracts (very common in the Arabic-speaking region) often contain discrepancies
between the two versions that nobody actually cross-checks, even though most contracts include a clause
stating "in case of conflict, version X shall prevail."

---

## Architecture

```
contract-intelligence/
├── data/
│   ├── raw_contracts/          # Sample contracts (PDF/DOCX)
│   ├── schema.json             # Definition of fields to extract
│   └── ground_truth/           # Manually labeled answers for evaluation
│
├── extraction/
│   ├── parser.py               # PDF/DOCX → text, with RTL/LTR direction handling
│   ├── chunker.py               # Splits text into clauses based on document structure
│   ├── language_detector.py    # Detects language per chunk (Arabic/English/mixed)
│   └── extractor.py            # Structured extraction via LLM (JSON schema)
│
├── alignment/
│   ├── embedder.py             # Multilingual embeddings (LaBSE / multilingual-e5)
│   ├── aligner.py               # Aligns Arabic clauses with their English counterparts
│   └── contradiction_checker.py # LLM-based semantic equivalence check
│
├── rag/
│   ├── vector_store.py         # Clause storage (Chroma/Qdrant)
│   ├── retriever.py             # Cross-lingual retrieval
│   └── qa_engine.py             # Question answering + guardrails
│
├── eval/
│   ├── extraction_eval.py      # Precision/recall for extraction
│   └── contradiction_eval.py   # Accuracy of contradiction detection
│
├── api/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── routers/
│   │   ├── extraction.py       # endpoints for uploading/extracting contracts
│   │   ├── alignment.py        # endpoints for discrepancy detection
│   │   └── qa.py                # endpoints for RAG Q&A
│   └── schemas.py               # Pydantic request/response models
│
├── frontend/
│   └── (React + Vite app, added in a later step)
│
└── CLAUDE.md                   # This file
```

---

## Technical Decisions

| Decision | Reason |
|---|---|
| **Extraction LLM:** Claude API with structured output (JSON schema) | More accurate than regex for free-form text, and flexible across varied clause phrasing |
| **Embeddings:** multilingual-e5 or LaBSE | Purpose-built for cross-lingual semantic similarity, not just literal translation matching |
| **Vector DB:** Chroma (local, simple for MVP) | Easy to run locally; can swap for Qdrant later if scale is needed |
| **Chunking:** by contract structure (clause-by-clause), not fixed-size | The clause is the logical unit of meaning in contracts; random splitting breaks context |
| **Guardrails:** "Not found in contract" instead of guessing | The system must never hallucinate legal information |
| **Backend/Frontend:** FastAPI (backend) + React (frontend), instead of Streamlit | Decouples the API from the UI, supports a richer interactive experience (side-by-side clause views, discrepancy highlighting) than Streamlit allows, and scales toward a real deployment |

---

## Target Schema (data/schema.json)

Core fields to extract from each contract:
- `parties`
- `effective_date`
- `duration`
- `financial_value`
- `termination_clauses`
- `penalty_clauses`
- `governing_law`
- `language_precedence_clause` (which version prevails in case of conflict, if present)

---

## Progress Tracker

- [ ] Phase 1: Data collection and preparation
- [ ] Phase 2: Extraction baseline
- [ ] Phase 3: Cross-version alignment + contradiction detection
- [ ] Phase 4: RAG for Q&A
- [ ] Phase 5: FastAPI backend + React frontend, and deployment
- [ ] Phase 6: Documentation (README + evaluation results)

---

## Notes for Future Sessions

- Any sample contract that isn't a real one must be marked as synthetic/template (to avoid privacy/legal issues)
- Evaluation must be reported with real numbers (precision/recall), not vague claims like "it works well"
- Prioritize the quality of the alignment/contradiction-detection component — this is the feature that differentiates the project from a generic RAG app
- The UI must correctly support RTL rendering for Arabic text

---

## Useful Commands

```bash
# Run evaluation
python eval/extraction_eval.py --contracts data/raw_contracts --ground-truth data/ground_truth

# Run the API locally
uvicorn api.main:app --reload

# Run the frontend locally (once added)
cd frontend && npm run dev
```

"""FastAPI app entrypoint for the bilingual contract intelligence API.

Run from the project root: uvicorn api.main:app --reload
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()  # so extraction/alignment/rag modules can read GEMINI_API_KEY at request time

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api.routers import alignment, extraction, qa, upload  # noqa: E402

app = FastAPI(title="Bilingual Contract Intelligence API")

# FRONTEND_URL defaults to Vite's local dev port; in production, set it to the deployed
# frontend's URL (e.g. the Vercel domain). Comma-separate multiple origins if needed,
# e.g. "https://app.vercel.app,https://staging.vercel.app".
_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
allow_origins = [origin.strip() for origin in _frontend_url.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extraction.router)
app.include_router(alignment.router)
app.include_router(qa.router)
app.include_router(upload.router)


@app.get("/")
def health_check() -> dict:
    return {"status": "ok"}

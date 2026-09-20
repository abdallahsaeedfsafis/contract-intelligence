# Deployment

Backend on [Render](https://render.com), frontend on [Vercel](https://vercel.com). This
project is deployment-ready but **not yet deployed** — nothing here has been provisioned.

## Backend (Render)

- **Start command:**
  ```
  uvicorn api.main:app --host 0.0.0.0 --port $PORT
  ```
  Render sets `$PORT` itself; don't hardcode a port.
- **Build command:** `pip install -r requirements.txt`
- **Required environment variables:**
  | Variable | Purpose |
  |---|---|
  | `GEMINI_API_KEY` | All extraction, alignment, and RAG calls go through the Gemini API. |
  | `FRONTEND_URL` | CORS allow-list (`api/main.py`). Set to the deployed Vercel URL; comma-separate multiple origins if needed (e.g. a preview + production domain). Defaults to `http://localhost:5173` if unset, which is only correct for local dev. |

- **Ephemeral storage caveat:** Render's free tier has no persistent disk. `chroma_db/`
  (the RAG vector index) and any uploaded contracts saved under `data/raw_contracts/`
  are wiped on every restart or redeploy. This is expected, not a bug:
  - `rag/vector_store.py`'s `build_contract_index()` is idempotent and is called
    on-demand before every question (`rag/qa_engine.py` via `api/routers/qa.py`), so a
    contract's index just gets rebuilt the first time someone asks about it after a
    fresh start - verified this works correctly starting from a completely empty
    `chroma_db/`.
  - Uploaded contracts (`POST /contracts/upload`), however, do **not** survive a
    restart - there's no re-upload/rebuild path for those the way there is for the
    vector index. If persistent uploads matter, this needs a real disk (Render's paid
    persistent disk add-on) or external storage (e.g. S3) before going further; out of
    scope for this pass.
- **Cold start:** Render's free tier spins down after inactivity and takes roughly
  30-60 seconds to wake back up on the next request. The first request after idle time
  will be slow (and may time out client-side if the frontend's request timeout is too
  short) - this is normal for the free tier, not a deploy issue.

## Frontend (Vercel)

- **Root directory:** `frontend/`
- **Build command:** `npm run build` · **Output directory:** `dist`
- **Required environment variable:**
  | Variable | Purpose |
  |---|---|
  | `VITE_API_URL` | Backend base URL (`frontend/src/api/client.js`). Set to the deployed Render URL. Defaults to `http://localhost:8000` if unset, which is only correct for local dev. Vite bakes this in at build time, so it must be set *before* building, not just at runtime. |

## Order of operations

1. Deploy the backend to Render first, without `FRONTEND_URL` set (or set to `*`
   temporarily) - you need its URL before configuring the frontend.
2. Deploy the frontend to Vercel with `VITE_API_URL` set to that Render URL.
3. Go back to the Render service and set `FRONTEND_URL` to the resulting Vercel URL,
   then redeploy the backend so CORS actually allows it.

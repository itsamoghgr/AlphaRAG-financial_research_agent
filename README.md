# AlphaRAG

A financial research agent that lazily ingests SEC 10-K and 10-Q filings on demand and answers questions about a company with span-level citations back to the source filing.

- **Backend**: FastAPI + SQLAlchemy 2.0 + Postgres with pgvector. Modular layers: `api` -> `services` -> `repositories` -> `infrastructure`.
- **Frontend**: Next.js 14 (App Router) + Tailwind + DaisyUI. Component-based, with an SSE hook for streamed stage events.
- **Retrieval**: hybrid (pgvector cosine + Postgres FTS), always scoped to one ticker.
- **Generation**: OpenAI `gpt-4o-mini` by default, with `[c1] [c2]` citation markers parsed and validated.

## How it works

1. User submits `(ticker, question)` from the chat UI.
2. Backend resolves the ticker to a CIK and checks whether we already have fresh filings for it in Postgres.
3. On a cache miss, the `IngestionService` downloads the latest 10-K and last two 10-Qs from EDGAR, splits them into sections, chunks them, embeds the chunks, and persists everything to Postgres+pgvector. Concurrent first-queries on the same ticker are serialized by a per-CIK Postgres advisory lock.
4. The `HybridRetriever` runs a vector + keyword search **scoped to that ticker only**.
5. The synthesizer prompts the LLM to answer using only the retrieved chunks, marking each claim with `[cN]`. A post-processor validates the markers and maps them back to source spans.
6. The frontend streams every stage live via SSE so the cold-start ingestion (~10-25s) doesn't feel broken.

See [docs/architecture.md](docs/architecture.md) for diagrams and the full plan.

## Prerequisites

- **Python 3.12** (this repo is set up against `/opt/anaconda3/bin/python3.12`)
- **Node.js 20+**
- **Postgres 16 with the pgvector extension**. Easiest path is Docker. Alternatives below.
- An **OpenAI API key**.

## Quick start

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY and SEC_USER_AGENT (must include a real email)

# 1. Start Postgres (Docker path)
docker compose up -d

# 2. Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn alpharag.main:app --reload --port 8000

# 3. Frontend (in a second terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

## If you don't have Docker

Three options:

1. **OrbStack** (recommended on macOS) — `brew install orbstack`, then `docker compose up -d` works as above.
2. **Homebrew Postgres + pgvector**:
   ```bash
   brew install postgresql@16 pgvector
   brew services start postgresql@16
   createuser -s alpharag && createdb -O alpharag alpharag
   psql -U alpharag -d alpharag -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```
3. **Cloud Postgres** with pgvector enabled (Supabase, Neon, Railway). Update `DATABASE_URL` in `.env`.

## Project layout

```
backend/                 # FastAPI app (modular layers)
  src/alpharag/
    api/                 # HTTP handlers (thin)
    services/            # Use cases / orchestration
    ingestion/           # EDGAR client, parser, chunker, embedder
    retrieval/           # Hybrid search
    generation/          # Prompts, synthesizer, citation parser
    llm/                 # Provider-agnostic LLM + embeddings
    db/                  # SQLAlchemy models + repositories
    core/                # Config, logging, errors
  scripts/               # warmup CLI, search CLI
  tests/                 # unit, integration, eval

frontend/                # Next.js 14 + DaisyUI (component-based)
  app/                   # Routes (App Router)
  components/            # Reusable UI components
  hooks/                 # useChatStream, useTickerValidator
  lib/                   # api, sse, types
```

## Development scripts

```bash
# Pre-warm common tickers so demo queries are instant
python -m scripts.warmup --tickers AAPL,MSFT,GOOGL,NVDA,TSLA

# Debug retrieval without the LLM
python -m scripts.search --ticker AAPL "what risk factors does the company face"

# Run unit + integration tests
pytest

# Run the eval harness
python -m tests.eval.run_eval
```

## License

MIT

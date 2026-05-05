#!/usr/bin/env bash
# Boot AlphaRAG locally: Postgres (Docker), backend (FastAPI), frontend (Next.js).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/bin/python3.12}"

log() { printf '\033[1;36m[start]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[start]\033[0m %s\n' "$*" >&2; }

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    log ".env not found — copying from .env.example. Edit it and re-run."
    cp .env.example .env
    err "Set OPENAI_API_KEY and SEC_USER_AGENT in .env, then re-run ./start.sh"
    exit 1
  else
    err ".env not found and no .env.example to copy from."
    exit 1
  fi
fi

# Load .env so backend tools (alembic, uvicorn) see the same config.
# Parse line-by-line instead of `source` so values with spaces (e.g.
# SEC_USER_AGENT="AlphaRAG Research email@example.com") don't get interpreted
# as commands when unquoted.
while IFS= read -r line || [[ -n "$line" ]]; do
  # skip blanks and comments
  [[ -z "${line// /}" || "${line#"${line%%[![:space:]]*}"}" == \#* ]] && continue
  # strip optional leading "export "
  line="${line#export }"
  key="${line%%=*}"
  val="${line#*=}"
  # only export if it actually looks like KEY=VALUE
  [[ "$key" == "$line" ]] && continue
  # strip one matching pair of surrounding quotes if present
  if [[ "$val" == \"*\" || "$val" == \'*\' ]]; then
    val="${val:1:${#val}-2}"
  fi
  export "$key=$val"
done < .env

# 1. Postgres via Docker
if command -v docker >/dev/null 2>&1; then
  log "Starting Postgres (docker compose up -d)…"
  docker compose up -d
  log "Waiting for Postgres to be healthy…"
  for _ in {1..30}; do
    status="$(docker inspect -f '{{.State.Health.Status}}' alpharag-postgres 2>/dev/null || echo "starting")"
    [[ "$status" == "healthy" ]] && break
    sleep 1
  done
  if [[ "${status:-}" != "healthy" ]]; then
    err "Postgres did not become healthy in time. Check 'docker compose logs postgres'."
    exit 1
  fi
else
  err "docker not found. Start Postgres yourself (see README) and re-run with SKIP_DOCKER=1 if you've already started it."
  [[ "${SKIP_DOCKER:-0}" == "1" ]] || exit 1
fi

# 2. Backend venv
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  log "Creating backend venv with $PYTHON_BIN…"
  if [[ ! -x "$PYTHON_BIN" ]]; then
    err "$PYTHON_BIN not found. Set PYTHON_BIN=/path/to/python3.12 and re-run."
    exit 1
  fi
  "$PYTHON_BIN" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -U pip
  pip install -e ".[dev]"
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

log "Running alembic migrations…"
alembic upgrade head

# 3. Launch backend + frontend, clean up on exit
PIDS=()
cleanup() {
  log "Shutting down…"
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

log "Starting backend on http://localhost:${BACKEND_PORT}…"
uvicorn alpharag.main:app --reload --port "$BACKEND_PORT" &
PIDS+=($!)

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  log "Installing frontend dependencies…"
  npm install
fi

log "Starting frontend on http://localhost:${FRONTEND_PORT}…"
PORT="$FRONTEND_PORT" npm run dev &
PIDS+=($!)

log "All services up. Press Ctrl-C to stop."
wait

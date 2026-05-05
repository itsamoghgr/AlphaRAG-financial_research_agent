#!/usr/bin/env bash
# Boot AlphaRAG locally: Postgres (Docker), backend (FastAPI), frontend (Next.js).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
# Capture PYTHON_BIN from the calling environment *before* .env is loaded,
# so a stale or unintended value in .env can't silently override it.
PYTHON_BIN_OVERRIDE="${PYTHON_BIN:-}"

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

# Resolve PYTHON_BIN: caller's env wins, then `python3.12` on PATH, then known
# install locations. This runs after .env so a missing/typo'd PYTHON_BIN in
# .env doesn't bite us.
resolve_python_bin() {
  local candidates=(
    "$PYTHON_BIN_OVERRIDE"
    "$(command -v python3.12 2>/dev/null || true)"
    /opt/homebrew/bin/python3.12
    /usr/local/bin/python3.12
    /opt/anaconda3/bin/python3.12
  )
  for c in "${candidates[@]}"; do
    [[ -n "$c" && -x "$c" ]] && { echo "$c"; return; }
  done
  return 1
}
PYTHON_BIN="$(resolve_python_bin || true)"

# 1. Postgres via Docker
if command -v docker >/dev/null 2>&1; then
  log "Starting Postgres (docker compose up -d)..."
  docker compose up -d
  # Wait for the *application* role/db to be ready, not just the daemon.
  # Postgres' built-in pg_isready healthcheck flips to "healthy" as soon as
  # the server accepts connections — which happens BEFORE the entrypoint's
  # init scripts have created POSTGRES_USER. So we probe with the real user.
  PG_USER="${POSTGRES_USER:-alpharag}"
  PG_DB="${POSTGRES_DB:-alpharag}"
  log "Waiting for Postgres role '$PG_USER' / db '$PG_DB' to be ready..."
  ready=0
  for _ in {1..60}; do
    if docker exec alpharag-postgres pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    err "Postgres role/db not ready after 60s. Check 'docker compose logs postgres'."
    err "If POSTGRES_USER in your .env changed since the volume was created, run: docker compose down -v && ./start.sh"
    exit 1
  fi
else
  err "docker not found. Start Postgres yourself (see README) and re-run with SKIP_DOCKER=1 if you've already started it."
  [[ "${SKIP_DOCKER:-0}" == "1" ]] || exit 1
fi

# 2. Backend venv
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  if [[ -z "$PYTHON_BIN" ]]; then
    err "No Python 3.12 interpreter found. Tried PATH and /opt/{homebrew,anaconda3}, /usr/local."
    err "Install Python 3.12 (e.g. 'brew install python@3.12') or set PYTHON_BIN=/path/to/python3.12 and re-run."
    exit 1
  fi
  log "Creating backend venv with $PYTHON_BIN..."
  "$PYTHON_BIN" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -U pip
  pip install -e ".[dev]"
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

log "Running alembic migrations..."
alembic upgrade head

# 3. Launch backend + frontend, clean up on exit
PIDS=()
cleanup() {
  log "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    [[ -n "${pid:-}" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

log "Starting backend on http://localhost:${BACKEND_PORT}..."
uvicorn alpharag.main:app --reload --port "$BACKEND_PORT" &
PIDS+=($!)

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  log "Installing frontend dependencies..."
  npm install
fi

log "Starting frontend on http://localhost:${FRONTEND_PORT}..."
PORT="$FRONTEND_PORT" npm run dev &
PIDS+=($!)

log "All services up. Press Ctrl-C to stop."
wait

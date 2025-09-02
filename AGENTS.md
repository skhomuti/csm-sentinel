# Repository Guidelines

These are the core guidelines for working in this repository.

## Project Structure & Modules
- `src/csm_bot/`: Bot logic (Telegram handlers, event parsing, RPC subscriptions).
- `src/tests/`: Pytest suite (unit/async tests, mocks).
- `abi/`: Contract ABIs loaded by the app.
- `.storage/`: Local persistence for Telegram state (mounted as a volume in Docker).
- `Dockerfile`, `docker-compose*.yml`: Containerization and local orchestration.
- `.env.sample.*`: Example environment files. Copy to `.env` for local runs.

## Build, Test, and Dev Commands
- Test: `uv run pytest -q`
- Run locally: `uv run python src/csm_bot/main.py` (requires `.env`).
- Docker: `docker compose up -d` (or `docker compose -f docker-compose-ethd.yml up -d` when co‑running with eth-docker).

## Coding Style & Naming
- Python ≥ 3.11; follow PEP 8; 4‑space indentation.
- Names: modules/functions `snake_case`, classes `CapWords`, constants `UPPER_SNAKE_CASE`.
- Prefer type hints and small, focused functions. Keep side effects in entrypoints (`main.py`, `rpc.py`, `jobs.py`).

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`.
- Tests live in `src/tests/` and are named `test_*.py` with clear, behavior‑driven names.
- Mock external I/O (Web3, `aiohttp`, env) using `unittest.mock` and `@patch.dict`.
- Run fast: avoid real network calls; rely on the prebuilt `.venv` via `uv run`.

## Commit & Pull Requests
- Commits: imperative mood, concise title, context in body (what/why), reference issues (e.g., `Closes #123`).
- PRs: include a summary, screenshots/logs of bot output if UI/UX changes, test plan (`uv run pytest -q`), and any env vars introduced/changed.
- Keep diffs minimal and focused; add/update `.env.sample.*` when touching configuration.

## Security & Configuration
- Never commit secrets. Use `.env` locally; base it on `.env.sample.*`.
- Key envs: `TOKEN`, `WEB3_SOCKET_PROVIDER`, contract addresses (CSM/ACCOUNTING/FEE_DISTRIBUTOR/VEBO), and URLs (`ETHERSCAN_URL`, `BEACONCHAIN_URL`, `CSM_UI_URL`).
- Persistence path is `.storage/persistence.pkl` (mounted volume in Docker).
- Admins: `ADMIN_IDS` (comma- or space-separated Telegram user IDs) to restrict admin-only commands.

# Agents Guide

This document captures practical conventions for working with this repo using agent tooling.

## Config & Env Access
- Prefer `get_config()` from `csm_bot.config` over ad‑hoc `os.getenv(...)`.
- Import once and reuse a module‑level `CFG = get_config()`.
- For tests that tweak env vars, call `get_config.cache_clear()` before re‑reading.
- When new envs are introduced, add them to `Config`, update `.env.sample.*`, and use `CFG` everywhere.

## Chain Reads & Versioning
- Always read contract state at the event’s block: pass `block_identifier=event.block`.
- Where pre‑state is needed, use `event.block - 1` intentionally and document it in code.

## Logging
- No `print`; use module‑level `logger` with structured context.
- Warn rather than fail for recoverable issues (e.g., version probe failures, optional filters).

## Typing
- Use built‑in types for unions and generics: `str | None`, `set[int]` (Python ≥ 3.11).
- Prefer precise types on public helpers; keep handlers small and focused.

## Adding Events/ABIs
- Place new ABIs under `abi/` and import them in `models.py`.
- Extend `EVENTS_TO_FOLLOW` via decorators in `events.py` and add matching entries in `texts.py` and `EVENT_DESCRIPTIONS`.
- Ensure `rpc.py` subscriptions/topics include the relevant ABIs and addresses from `CFG`.
- Maintain the invariant checked in `main.py` that events, messages, and descriptions are in sync.

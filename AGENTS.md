# Instructions for Codex agents

## Running tests

This repository contains a prebuilt Python virtual environment in `.venv` with all required dependencies. Use this environment when running the tests so that imports resolve correctly and no network access is needed.

To execute the test suite:

```bash
# Option 1: Use `uv run` which automatically uses `.venv`
uv run pytest -q

# Option 2: Activate the virtual environment directly
source .venv/bin/activate
pytest -q
```

Running tests outside of `.venv` or without `uv run` may fail due to missing packages. No additional `pip install` commands are necessary.

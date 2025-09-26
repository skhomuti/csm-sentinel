"""Shared pytest configuration for the test suite."""

from pathlib import Path

from dotenv import load_dotenv

# Load local environment variables before tests run.
env_file = Path(".env")
if env_file.exists():
    load_dotenv(env_file, override=False)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark tests that require a locally forked Anvil node",
    )

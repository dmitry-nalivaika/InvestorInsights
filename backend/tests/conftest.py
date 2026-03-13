"""Shared test fixtures for the InvestorInsights backend test suite."""

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio as the async backend for tests."""
    return "asyncio"

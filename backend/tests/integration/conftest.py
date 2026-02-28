"""Fixtures for LLM integration tests.

These tests require OPENAI_API_KEY and ANTHROPIC_API_KEY to be set.
Run with: uv run pytest -m integration
Skip with: uv run pytest -m "not integration"
"""

from __future__ import annotations

import os

import dspy
import pytest


@pytest.fixture(scope="session")
def require_api_keys():
    """Skip integration tests if API keys are not set."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")


@pytest.fixture(scope="session")
def generation_lm(require_api_keys):
    return dspy.LM(model="openai/gpt-5.2", temperature=None, max_tokens=None)


@pytest.fixture(scope="session")
def evaluation_lm(require_api_keys):
    return dspy.LM(model="anthropic/claude-sonnet-4-6", temperature=0.1, max_tokens=1500)


@pytest.fixture
def pipeline():
    from app.services.dspy_modules import ExamPipeline

    return ExamPipeline(best_of_n=3)

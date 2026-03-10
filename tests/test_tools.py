"""
Tool integration tests for My Pocket Guide.

These tests call live GCP services (Vertex AI RAG).
Requires valid .env with GOOGLE_CLOUD_PROJECT, RAG_LOCATION, RAG_CORPUS.

Run:
    pytest tests/test_tools.py -v
    pytest tests/test_tools.py -v -m "not integration"  # skip live calls
"""

import os
import pytest
from dotenv import load_dotenv
from unittest.mock import AsyncMock, patch

load_dotenv()

from backend.tools.rag_tool import rag_search
from backend.tools.identify_tool import identify_exhibit


# ── RAG Search Tests (live GCP calls) ────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_search_known_exhibit():
    result = await rag_search("Hope the blue whale size and history")
    assert result["found"] is True
    assert len(result["facts"]) > 0
    assert "25.2" in result["facts"] or "blue whale" in result["facts"].lower()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_search_returns_dict_for_any_query():
    result = await rag_search("purple elephant from Mars exhibit")
    assert isinstance(result, dict)
    assert "found" in result
    assert "facts" in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_search_returns_dict():
    result = await rag_search("whale")
    assert isinstance(result, dict)
    assert "found" in result
    assert "facts" in result


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_search_includes_score():
    result = await rag_search("blue whale heart weight")
    assert result["found"] is True
    assert "best_score" in result
    assert result["best_score"] > 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_search_facts_are_factual():
    result = await rag_search("blue whale heart weight")
    assert result["found"] is True
    assert "180" in result["facts"]


# ── RAG Search Tests (mocked — no GCP needed) ────────────────────────────────

@pytest.mark.asyncio
async def test_rag_search_error_returns_safe_dict():
    """If RAG fails, rag_search should return a safe dict, never raise."""
    with patch("backend.tools.rag_tool.rag.retrieval_query", side_effect=Exception("network error")):
        result = await rag_search("anything")
        assert isinstance(result, dict)
        assert result["found"] is False
        assert "facts" in result


# ── Identify Exhibit Tests (no GCP needed — pure logic) ──────────────────────

class MockToolContext:
    """Minimal ToolContext mock for testing state writes."""
    def __init__(self):
        self.state = {}


@pytest.mark.asyncio
async def test_identify_exhibit_exact_match():
    ctx = MockToolContext()
    result = await identify_exhibit("Hope the Blue Whale", ctx)
    assert result["status"] == "success"
    assert result["exhibit_id"] == "hope_blue_whale"
    assert ctx.state["current_exhibit_id"] == "hope_blue_whale"
    assert ctx.state["current_gallery"] == "Echoes of the Deep"


@pytest.mark.asyncio
async def test_identify_exhibit_keyword_alias():
    ctx = MockToolContext()
    result = await identify_exhibit("the big thumb", ctx)
    assert result["status"] == "success"
    assert result["exhibit_id"] == "really_good"


@pytest.mark.asyncio
async def test_identify_exhibit_case_insensitive():
    ctx = MockToolContext()
    result = await identify_exhibit("mona lisa", ctx)
    assert result["status"] == "success"
    assert result["exhibit_id"] == "mona_lisa"


@pytest.mark.asyncio
async def test_identify_exhibit_partial_name():
    ctx = MockToolContext()
    result = await identify_exhibit("Antikythera", ctx)
    assert result["status"] == "success"
    assert result["exhibit_id"] == "antikythera_mechanism"


@pytest.mark.asyncio
async def test_identify_exhibit_unknown_returns_error():
    ctx = MockToolContext()
    result = await identify_exhibit("completely unknown thing xyz", ctx)
    assert result["status"] == "error"
    # State should NOT be written on failure
    assert "current_exhibit_id" not in ctx.state


@pytest.mark.asyncio
async def test_identify_exhibit_short_string_guard():
    """Strings under 4 chars should not cause false positive matches."""
    ctx = MockToolContext()
    result = await identify_exhibit("hi", ctx)
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_identify_all_16_exhibits():
    """Regression test — every canonical exhibit name must resolve correctly."""
    from backend.tools.exhibit_data import EXHIBITS
    failures = []
    for exhibit_id, data in EXHIBITS.items():
        ctx = MockToolContext()
        result = await identify_exhibit(data["name"], ctx)
        if result["status"] != "success" or result["exhibit_id"] != exhibit_id:
            failures.append(f"{data['name']} → {result}")
    assert failures == [], f"Failed exhibits:\n" + "\n".join(failures)
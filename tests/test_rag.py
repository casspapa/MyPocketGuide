import os
import pytest
from dotenv import load_dotenv

load_dotenv()

import vertexai
from vertexai.preview import rag

@pytest.fixture(scope="module")
def rag_corpus():
    vertexai.init(
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=os.getenv("RAG_LOCATION")
    )
    return os.getenv("RAG_CORPUS")

def test_rag_returns_results(rag_corpus):
    results = rag.retrieval_query(
        rag_resources=[rag.RagResource(rag_corpus=rag_corpus)],
        text="How big is Hope the blue whale?",
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
    )
    assert len(results.contexts.contexts) > 0

def test_rag_returns_correct_exhibit(rag_corpus):
    results = rag.retrieval_query(
        rag_resources=[rag.RagResource(rag_corpus=rag_corpus)],
        text="Hope blue whale size weight",
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
    )
    combined_text = " ".join([c.text for c in results.contexts.contexts])
    assert "hope_blue_whale" in combined_text.lower() or "25.2" in combined_text

def test_rag_returns_factual_content(rag_corpus):
    results = rag.retrieval_query(
        rag_resources=[rag.RagResource(rag_corpus=rag_corpus)],
        text="blue whale heart weight",
        rag_retrieval_config=rag.RagRetrievalConfig(top_k=3)
    )
    combined_text = " ".join([c.text for c in results.contexts.contexts])
    assert "180" in combined_text

import pytest
import tempfile
import shutil
from arvan_project.parser.tree_parser import MarkdownTreeParser
from arvan_project.storage.bm25_index import BM25Index
from arvan_project.storage.chroma_store import ChromaVectorStore, SimpleHashEmbeddingFunction
from arvan_project.storage.hybrid_store import HybridSearchStore

DOC_CONTENT = """# AI Architecture

Overview of AI models and search algorithms.

## Vector Search
Dense embeddings capture deep semantic meaning using cosine similarity.

## Lexical Search
BM25 algorithm performs keyword matching based on term frequency and document frequency.

## Hybrid Search
Combines dense vectors and BM25 using an alpha parameter for optimal ranking.
"""


@pytest.fixture
def temp_env():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_bm25_index_basic():
    parser = MarkdownTreeParser()
    doc = parser.parse_text(DOC_CONTENT, doc_id="ai_doc")

    index = BM25Index()
    index.add_nodes(doc.all_nodes())

    assert len(index) == 4

    # Search for term specific to BM25
    scores = index.search("BM25 algorithm keyword", top_k=2)
    assert len(scores) > 0
    top_node_id = list(scores.keys())[0]
    assert "Lexical Search" in top_node_id

    # Test delete
    index.delete_node(top_node_id)
    assert len(index) == 3


def test_hybrid_search_alpha_weighting(temp_env):
    parser = MarkdownTreeParser()
    doc = parser.parse_text(DOC_CONTENT, doc_id="ai_doc")

    vector_store = ChromaVectorStore(
        persist_directory=f"{temp_env}/chroma",
        embedding_fn=SimpleHashEmbeddingFunction(),
    )
    bm25_index = BM25Index()
    registry_path = f"{temp_env}/registry.json"

    store = HybridSearchStore(
        vector_store=vector_store,
        bm25_index=bm25_index,
        registry_path=registry_path,
    )

    # Ingest
    diff = store.ingest_document(doc)
    assert len(diff.added) == 4

    # Search with alpha = 0.0 (Pure BM25)
    results_bm25 = store.search(query="frequency BM25", alpha=0.0, top_k=3)
    assert len(results_bm25) > 0
    assert "Lexical Search" in results_bm25[0].title
    assert results_bm25[0].bm25_score is not None

    # Search with alpha = 1.0 (Pure Dense)
    results_dense = store.search(query="semantic meaning", alpha=1.0, top_k=3)
    assert len(results_dense) > 0
    assert results_dense[0].dense_score is not None

    # Search with alpha = 0.5 (Hybrid)
    results_hybrid = store.search(query="alpha parameter hybrid", alpha=0.5, top_k=3)
    assert len(results_hybrid) > 0
    assert "Hybrid Search" in results_hybrid[0].title
    assert results_hybrid[0].score > 0.0


def test_incremental_ingest_via_store(temp_env):
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_CONTENT, doc_id="ai_doc")

    store = HybridSearchStore(
        vector_store=ChromaVectorStore(
            persist_directory=f"{temp_env}/chroma",
            embedding_fn=SimpleHashEmbeddingFunction(),
        ),
        bm25_index=BM25Index(),
        registry_path=f"{temp_env}/registry.json",
    )

    # First ingestion
    diff1 = store.ingest_document(doc_v1)
    assert len(diff1.nodes_needing_embedding) == 4

    # Second ingestion of the same text -> zero re-embeddings!
    diff2 = store.ingest_document(doc_v1)
    assert len(diff2.nodes_needing_embedding) == 0
    assert len(diff2.unchanged) == 4

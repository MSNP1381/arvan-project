import pytest
import tempfile
import shutil
from pathlib import Path
from arvan_project.parser.loaders import UniversalDocumentLoader
from arvan_project.storage.hybrid_store import HybridSearchStore
from arvan_project.storage.chroma_store import ChromaVectorStore
from arvan_project.storage.bm25_index import BM25Index


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_document_full_deletion_lifecycle(temp_dir):
    # Isolated test store
    db_dir = temp_dir / "chroma"
    reg_path = temp_dir / "registry.json"

    chroma = ChromaVectorStore(persist_directory=str(db_dir))
    bm25 = BM25Index()
    store = HybridSearchStore(
        vector_store=chroma,
        bm25_index=bm25,
        registry_path=str(reg_path),
    )

    # 1. Create and ingest document
    txt_file = temp_dir / "ephemeral_policy.txt"
    txt_file.write_text(
        "Confidential Protocol Zebra 9988: strictly deleted upon completion.",
        encoding="utf-8",
    )

    loader = UniversalDocumentLoader()
    doc = loader.load_file(txt_file, doc_id="ephemeral_doc")
    diff = store.ingest_document(doc)
    assert len(diff.nodes_needing_embedding) > 0

    # Verify search finds it
    results_before = store.search("Protocol Zebra 9988", top_k=3)
    assert any(r.doc_id == "ephemeral_doc" for r in results_before)
    assert "ephemeral_doc" in store.list_documents()

    # 2. Delete document
    deleted = store.delete_document("ephemeral_doc")
    assert deleted is True

    # 3. Verify it is completely purged from store & BM25 & Chroma
    assert "ephemeral_doc" not in store.list_documents()
    assert store.get_document("ephemeral_doc") is None

    results_after = store.search("Protocol Zebra 9988", top_k=3)
    assert not any(r.doc_id == "ephemeral_doc" for r in results_after)

    # Attempting to delete again returns False
    assert store.delete_document("ephemeral_doc") is False

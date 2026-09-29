import pytest
import tempfile
import shutil
from langchain_core.messages import HumanMessage, AIMessage
from arvan_project.parser.tree_parser import MarkdownTreeParser
from arvan_project.storage.bm25_index import BM25Index
from arvan_project.storage.chroma_store import ChromaVectorStore, SimpleHashEmbeddingFunction
from arvan_project.storage.hybrid_store import HybridSearchStore
from arvan_project.agent.tools import (
    search_documentation,
    get_document_toc,
    read_section,
    list_indexed_documents,
    set_store,
)
from arvan_project.agent.graph import create_agent_graph

DOC_CONTENT = """# Cloud Platform

Cloud services documentation.

## Virtual Machines
Deploy compute instances with custom CPU and RAM.

## Object Storage
S3-compatible bucket storage for files and assets.
"""


@pytest.fixture
def agent_env():
    temp_dir = tempfile.mkdtemp()
    store = HybridSearchStore(
        vector_store=ChromaVectorStore(
            persist_directory=f"{temp_dir}/chroma",
            embedding_fn=SimpleHashEmbeddingFunction(),
        ),
        bm25_index=BM25Index(),
        registry_path=f"{temp_dir}/registry.json",
    )
    parser = MarkdownTreeParser()
    doc = parser.parse_text(DOC_CONTENT, doc_id="cloud_doc")
    store.ingest_document(doc)
    set_store(store)

    yield store
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_tool_list_indexed_documents(agent_env):
    output = list_indexed_documents.invoke({})
    assert "cloud_doc" in output


def test_tool_get_document_toc(agent_env):
    output = get_document_toc.invoke({"doc_id": "cloud_doc"})
    assert "Virtual Machines" in output
    assert "Object Storage" in output
    assert "(H2, Lines" in output


def test_tool_read_section(agent_env):
    output = read_section.invoke(
        {"doc_id": "cloud_doc", "section_path": "Cloud Platform > Object Storage"}
    )
    assert "S3-compatible bucket storage" in output


def test_tool_search_documentation(agent_env):
    output = search_documentation.invoke(
        {"query": "virtual machines compute instances", "alpha": 0.5, "top_k": 2}
    )
    assert "Citation:" in output
    assert "Virtual Machines" in output


def test_agent_graph_creation():
    # Verify graph compiles without error
    app = create_agent_graph()
    assert app is not None


def test_tool_escalate_to_support():
    from arvan_project.agent.tools import escalate_to_support

    res = escalate_to_support.invoke({
        "service_type": "gpu",
        "details": "User requested NVIDIA A100 GPU pricing and quota.",
    })
    # Returns Persian confirmation message
    assert "پشتیبانی" in res


import io
import pytest
from fastapi.testclient import TestClient
from arvan_project.api import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "indexed_documents" in data


def test_api_list_documents(client):
    res = client.get("/api/documents")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        assert "doc_id" in data[0]
        assert "total_nodes" in data[0]


def test_api_search_endpoint(client):
    res = client.post("/api/search", json={"query": "Block Storage", "alpha": 0.8, "top_k": 2})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "score" in first
        assert "citation" in first
        assert "path_str" in first


def test_api_query_endpoint(client):
    res = client.post("/api/query", json={"query": "IOPS block storage", "use_agent": False})
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "citations" in data
    assert len(data["answer"]) > 0


def test_api_pricing_calculator(client):
    res = client.post(
        "/api/calculator/price",
        json={
            "cpu_cores": 4,
            "ram_gb": 8,
            "storage_gb": 100,
            "region": "iran",
            "tier": "standard",
            "storage_type": "ssd",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_hourly_toman"] > 0
    assert data["total_monthly_toman"] > 0
    assert len(data["breakdown"]) >= 3


def test_api_document_ingest_and_delete_cycle(client):
    # Ingest a temporary markdown file via multipart upload
    content = b"# API Test Document\n\nTesting temporary ingestion via FastAPI endpoint."
    file_tuple = ("api_test_doc.md", io.BytesIO(content), "text/markdown")

    ingest_res = client.post(
        "/api/documents/ingest",
        files={"file": file_tuple},
        data={"doc_id": "api_test_doc"},
    )
    assert ingest_res.status_code == 200
    data = ingest_res.json()
    assert data["doc_id"] == "api_test_doc"
    assert data["total_nodes"] >= 1

    # Verify TOC endpoint
    toc_res = client.get("/api/documents/api_test_doc/toc")
    assert toc_res.status_code == 200
    assert toc_res.json()["doc_id"] == "api_test_doc"

    # Delete the document
    del_res = client.delete("/api/documents/api_test_doc")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Confirm 404 on deleted document TOC
    del_toc_res = client.get("/api/documents/api_test_doc/toc")
    assert del_toc_res.status_code == 404

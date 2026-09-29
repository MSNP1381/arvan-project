import pytest
from pathlib import Path
from arvan_project.parser.loaders import UniversalDocumentLoader


def test_universal_loader_markdown():
    loader = UniversalDocumentLoader()
    doc_path = Path("docs/sample_architecture.md")
    assert doc_path.exists()

    doc = loader.load_file(doc_path, doc_id="test_sample")
    assert doc.doc_id == "test_sample"
    assert len(doc.all_nodes()) > 5
    # Verify hierarchical AST headings were preserved
    headings = [n.title for n in doc.all_nodes()]
    assert "Compute Engine" in headings
    assert "Instance Types" in headings


import tempfile

def test_universal_loader_text():
    with tempfile.TemporaryDirectory() as temp_dir:
        txt_file = Path(temp_dir) / "sample_guide.txt"
        txt_file.write_text(
            "Arvan Cloud Object Storage provides 99.999999999% durability.\n"
            "It supports S3-compatible APIs, multipart uploads, and lifecycle rules.\n\n"
            "Security is enforced with TLS 1.3 encryption and bucket policies.",
            encoding="utf-8",
        )

        loader = UniversalDocumentLoader(chunk_size=150, chunk_overlap=20)
        doc = loader.load_file(txt_file, doc_id="text_guide")

    assert doc.doc_id == "text_guide"
    assert len(doc.all_nodes()) >= 2
    # Verify chunks are wrapped into TOCNode instances
    for node in doc.all_nodes():
        assert node.doc_id == "text_guide"
        assert len(node.path) >= 1


def test_universal_loader_pdf():
    pdf_path = Path("interview-task.pdf")
    if not pdf_path.exists():
        pytest.skip("interview-task.pdf not found in root")

    loader = UniversalDocumentLoader(chunk_size=500, chunk_overlap=50)
    doc = loader.load_file(pdf_path, doc_id="interview_pdf")

    assert doc.doc_id == "interview_pdf"
    assert len(doc.all_nodes()) >= 4
    # Check that PDF pages are captured with breadcrumbs
    page_nodes = [n for n in doc.all_nodes() if n.is_leaf]
    assert len(page_nodes) > 0
    assert "Page" in page_nodes[0].title

import pytest
from arvan_project.parser.tree_parser import MarkdownTreeParser
from arvan_project.parser.models import TOCNode

SAMPLE_MARKDOWN = """# Project Documentation

Welcome to the project documentation.

## Architecture

Our architecture is composed of several microservices.

### Ingestion Service

The ingestion service handles markdown parsing and tree generation.

```python
# This is a python comment, not a heading!
def parse():
    pass
```

### Storage Service

The storage service stores vectors in ChromaDB and indexes words with BM25.

## Deployment

Deploy using Docker Compose or Kubernetes.
"""


def test_markdown_tree_parser_hierarchy():
    parser = MarkdownTreeParser()
    doc = parser.parse_text(SAMPLE_MARKDOWN, doc_id="test_doc", title="Test Doc")

    assert doc.doc_id == "test_doc"
    assert doc.title == "Test Doc"
    assert len(doc.root_nodes) == 1

    root = doc.root_nodes[0]
    assert root.title == "Project Documentation"
    assert root.level == 1
    assert not root.is_leaf
    assert len(root.children) == 2  # Architecture, Deployment

    arch = root.children[0]
    assert arch.title == "Architecture"
    assert arch.level == 2
    assert arch.path == ["Project Documentation", "Architecture"]
    assert arch.path_str == "Project Documentation > Architecture"
    assert len(arch.children) == 2  # Ingestion Service, Storage Service

    ingestion = arch.children[0]
    assert ingestion.title == "Ingestion Service"
    assert ingestion.level == 3
    assert ingestion.path_str == "Project Documentation > Architecture > Ingestion Service"
    assert ingestion.is_leaf
    # Verify code comment was NOT treated as heading
    assert "# This is a python comment" in ingestion.content

    deployment = root.children[1]
    assert deployment.title == "Deployment"
    assert deployment.level == 2
    assert deployment.is_leaf


def test_toc_node_flatten_and_embeddable_text():
    parser = MarkdownTreeParser()
    doc = parser.parse_text(SAMPLE_MARKDOWN, doc_id="test_doc")

    all_nodes = doc.all_nodes()
    assert len(all_nodes) == 5  # Root, Architecture, Ingestion, Storage, Deployment

    leaf_nodes = doc.get_leaf_nodes()
    assert len(leaf_nodes) >= 3

    # Check embeddable text prepends the path
    ingestion_node = [n for n in all_nodes if n.title == "Ingestion Service"][0]
    emb_text = ingestion_node.get_embeddable_text()
    assert emb_text.startswith("Section: Project Documentation > Architecture > Ingestion Service")
    assert "The ingestion service handles markdown parsing" in emb_text


def test_markdown_frontmatter_and_persian_parsing():
    content = """---
title: "اتصال به ابرک"
url: "https://docs.arvancloud.ir/fa/cloud-server/instance/connection/"
description: "راهنمای اتصال به ابرک‌های آروان"
---

# اتصال به ابرک

توضیحات اتصال به سرور ابری آروان.

## اتصال با SSH

برای اتصال از ترمینال لینوکس یا PuTTY استفاده کنید.
"""
    parser = MarkdownTreeParser()
    doc = parser.parse_text(content, doc_id="cloud-server/instance/connection")

    assert doc.title == "اتصال به ابرک"
    assert doc.url == "https://docs.arvancloud.ir/fa/cloud-server/instance/connection/"
    assert doc.description == "راهنمای اتصال به ابرک‌های آروان"
    assert len(doc.root_nodes) == 1

    root = doc.root_nodes[0]
    assert root.title == "اتصال به ابرک"
    assert root.url == "https://docs.arvancloud.ir/fa/cloud-server/instance/connection/"
    assert len(root.children) == 1

    ssh_node = root.children[0]
    assert ssh_node.title == "اتصال با SSH"
    assert ssh_node.url == "https://docs.arvancloud.ir/fa/cloud-server/instance/connection/"
    assert "PuTTY" in ssh_node.content

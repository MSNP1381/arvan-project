import pytest
from arvan_project.parser.tree_parser import MarkdownTreeParser
from arvan_project.parser.tree_diff import TreeDiffEngine

DOC_V1 = """# System Guide

General overview of our system.

## Ingestion
Ingestion parses markdown into trees.

## Storage
Vectors are stored in database.
"""

# V2:
# - Ingestion is unchanged
# - Storage content is MODIFIED
# - New section 'Monitoring' is ADDED
DOC_V2 = """# System Guide

General overview of our system.

## Ingestion
Ingestion parses markdown into trees.

## Storage
Vectors are stored in ChromaDB and cached in Redis.

## Monitoring
Prometheus and Grafana are used.
"""

# V3:
# - Storage is REMOVED
DOC_V3 = """# System Guide

General overview of our system.

## Ingestion
Ingestion parses markdown into trees.
"""

# V4:
# - Heading 'Ingestion' renamed to 'Data Ingestion', content identical
DOC_V4 = """# System Guide

General overview of our system.

## Data Ingestion
Ingestion parses markdown into trees.
"""


def test_tree_diff_initial():
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_V1, doc_id="guide")
    diff = TreeDiffEngine.compute_diff(None, doc_v1)

    assert len(diff.added) == 3  # Root, Ingestion, Storage
    assert len(diff.modified) == 0
    assert len(diff.deleted) == 0
    assert len(diff.unchanged) == 0


def test_tree_diff_identical():
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_V1, doc_id="guide")
    doc_v1_again = parser.parse_text(DOC_V1, doc_id="guide")
    diff = TreeDiffEngine.compute_diff(doc_v1, doc_v1_again)

    assert len(diff.unchanged) == 3
    assert len(diff.added) == 0
    assert len(diff.modified) == 0
    assert len(diff.deleted) == 0
    assert len(diff.nodes_needing_embedding) == 0


def test_tree_diff_modified_and_added():
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_V1, doc_id="guide")
    doc_v2 = parser.parse_text(DOC_V2, doc_id="guide")
    diff = TreeDiffEngine.compute_diff(doc_v1, doc_v2)

    # Ingestion and Root overview should be unchanged
    unchanged_titles = [n.title for n in diff.unchanged]
    assert "Ingestion" in unchanged_titles
    assert "System Guide" in unchanged_titles

    # Storage should be modified
    assert len(diff.modified) == 1
    old_mod, new_mod = diff.modified[0]
    assert old_mod.title == "Storage"
    assert new_mod.title == "Storage"

    # Monitoring should be added
    assert len(diff.added) == 1
    assert diff.added[0].title == "Monitoring"

    # Only Storage and Monitoring need re-embedding
    needs_emb = [n.title for n in diff.nodes_needing_embedding]
    assert "Storage" in needs_emb
    assert "Monitoring" in needs_emb
    assert "Ingestion" not in needs_emb


def test_tree_diff_deleted():
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_V1, doc_id="guide")
    doc_v3 = parser.parse_text(DOC_V3, doc_id="guide")
    diff = TreeDiffEngine.compute_diff(doc_v1, doc_v3)

    deleted_titles = [n.title for n in diff.deleted]
    assert "Storage" in deleted_titles
    assert "guide::System Guide > Storage" in diff.node_ids_to_delete


def test_tree_diff_renamed_or_moved():
    parser = MarkdownTreeParser()
    doc_v1 = parser.parse_text(DOC_V1, doc_id="guide")
    doc_v4 = parser.parse_text(DOC_V4, doc_id="guide")
    diff = TreeDiffEngine.compute_diff(doc_v1, doc_v4)

    # Ingestion was renamed to Data Ingestion with identical content
    assert len(diff.renamed_or_moved) == 1
    old_n, new_n = diff.renamed_or_moved[0]
    assert old_n.title == "Ingestion"
    assert new_n.title == "Data Ingestion"
    # Neither should be in added or deleted
    assert not any(n.title == "Data Ingestion" for n in diff.added)

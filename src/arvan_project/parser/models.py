from __future__ import annotations
import hashlib
from typing import Any
from pydantic import BaseModel, Field


def compute_sha256(text: str) -> str:
    """Compute deterministic SHA-256 hash of text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class TOCNode(BaseModel):
    """Represents a node in the Markdown Table of Contents (TOC) tree."""

    id: str = Field(description="Deterministic ID for this node")
    doc_id: str = Field(description="Document ID this node belongs to")
    title: str = Field(description="Heading title")
    level: int = Field(description="Heading depth (1 for H1, 2 for H2, etc.)")
    path: list[str] = Field(
        default_factory=list, description="Breadcrumb list of headings"
    )
    path_str: str = Field(
        default="", description="Breadcrumb string, e.g. Root > Section > Subsection"
    )
    content: str = Field(
        default="", description="Body content directly under this heading"
    )
    content_hash: str = Field(
        default="", description="SHA-256 hash of the node content"
    )
    line_start: int = Field(default=0, description="Starting line in source (1-indexed)")
    line_end: int = Field(default=0, description="Ending line in source (1-indexed)")
    children: list[TOCNode] = Field(
        default_factory=list, description="Subsections under this node"
    )
    is_leaf: bool = Field(default=True, description="Whether this node has no children")
    url: str = Field(default="", description="Documentation URL for this section")

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash and self.content:
            self.content_hash = compute_sha256(self.content)
        if not self.path_str and self.path:
            self.path_str = " > ".join(self.path)

    def get_embeddable_text(self) -> str:
        """Returns contextual text including breadcrumbs for high-quality embedding."""
        header = f"Section: {self.path_str}" if self.path_str else f"Section: {self.title}"
        body = self.content.strip()
        if not body:
            return header
        return f"{header}\n\n{body}"

    def flatten(self) -> list[TOCNode]:
        """Flatten this node and all its descendants into a flat list in preorder."""
        nodes = [self]
        for child in self.children:
            nodes.extend(child.flatten())
        return nodes


class DiffResult(BaseModel):
    """Result of an incremental structural diff between two versions of a document tree."""

    doc_id: str
    unchanged: list[TOCNode] = Field(default_factory=list)
    added: list[TOCNode] = Field(default_factory=list)
    modified: list[tuple[TOCNode, TOCNode]] = Field(default_factory=list)  # (old, new)
    deleted: list[TOCNode] = Field(default_factory=list)
    renamed_or_moved: list[tuple[TOCNode, TOCNode]] = Field(default_factory=list)  # (old, new)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted or self.renamed_or_moved)

    @property
    def nodes_needing_embedding(self) -> list[TOCNode]:
        """Returns the list of new or modified nodes that actually require re-embedding."""
        res: list[TOCNode] = []
        for node in self.added:
            if node.content.strip():
                res.append(node)
        for _old, new_node in self.modified:
            if new_node.content.strip():
                res.append(new_node)
        return res

    @property
    def node_ids_to_delete(self) -> list[str]:
        """IDs of nodes to remove from the vector/BM25 index."""
        to_delete: list[str] = [n.id for n in self.deleted]
        for old_node, _new_node in self.modified:
            to_delete.append(old_node.id)
        return to_delete


class MarkdownDocument(BaseModel):
    """Represents a parsed Markdown document with its TOC tree."""

    doc_id: str
    title: str = ""
    url: str = ""
    description: str = ""
    raw_content: str = ""
    root_nodes: list[TOCNode] = Field(default_factory=list)
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash and self.raw_content:
            self.content_hash = compute_sha256(self.raw_content)

    def all_nodes(self) -> list[TOCNode]:
        """Return all nodes in the document tree."""
        result = []
        for root in self.root_nodes:
            result.extend(root.flatten())
        return result

    def get_leaf_nodes(self) -> list[TOCNode]:
        """Return only leaf nodes (or non-empty content nodes)."""
        return [n for n in self.all_nodes() if n.is_leaf or n.content.strip()]

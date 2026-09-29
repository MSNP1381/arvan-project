from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field
from arvan_project.parser.models import TOCNode


class SearchResult(BaseModel):
    """Represents a single retrieved chunk with hierarchical metadata."""

    doc_id: str
    node_id: str
    title: str
    path_str: str
    content: str
    score: float = Field(description="Combined hybrid relevance score")
    dense_score: Optional[float] = Field(
        default=None, description="Normalized dense cosine similarity"
    )
    bm25_score: Optional[float] = Field(
        default=None, description="Normalized BM25 lexical score"
    )
    line_start: int = 0
    line_end: int = 0
    url: Optional[str] = Field(default="", description="Documentation URL")

    def format_citation(self) -> str:
        """Format node breadcrumb citation."""
        base_cit = f"{self.doc_id} > {self.path_str} (lines {self.line_start}-{self.line_end})"
        if self.url:
            return f"{base_cit} | Link: {self.url}"
        return base_cit


class BaseVectorStore(ABC):
    """Abstract interface for vector database storage."""

    @abstractmethod
    def add_nodes(self, nodes: list[TOCNode]) -> None:
        """Add or update nodes in vector storage."""
        pass

    @abstractmethod
    def delete_nodes(self, node_ids: list[str]) -> None:
        """Remove nodes by their deterministic IDs."""
        pass

    @abstractmethod
    def update_node_metadata(
        self, old_id: str, new_id: str, new_path_str: str, new_title: str
    ) -> None:
        """Update node metadata (e.g. renamed/moved section) without re-embedding."""
        pass

    @abstractmethod
    def search_dense(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Perform dense vector semantic similarity search."""
        pass

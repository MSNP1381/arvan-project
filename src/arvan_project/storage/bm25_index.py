from __future__ import annotations
import re
from typing import Optional
from rank_bm25 import BM25Okapi
from arvan_project.parser.models import TOCNode


class BM25Index:
    """In-memory BM25 lexical index with incremental node updates."""

    TOKEN_REGEX = re.compile(r"\w+")

    def __init__(self) -> None:
        # Maps node_id -> {"node": TOCNode, "tokens": list[str]}
        self._corpus: dict[str, dict] = {}
        self._bm25: Optional[BM25Okapi] = None
        self._node_id_list: list[str] = []
        self._is_dirty: bool = True

    def tokenize(self, text: str) -> list[str]:
        """Fast lowercase word tokenizer with Persian character normalization."""
        normalized = (
            text.replace("ي", "ی")
            .replace("ك", "ک")
            .replace("\u200c", " ")
            .replace("‌", " ")
        )
        return [match.group(0).lower() for match in self.TOKEN_REGEX.finditer(normalized)]

    def add_node(self, node: TOCNode) -> None:
        """Add or update a TOCNode in the BM25 index."""
        # Include breadcrumbs and content for lexical matching
        searchable_text = f"{node.path_str} {node.content}"
        tokens = self.tokenize(searchable_text)
        self._corpus[node.id] = {
            "node": node,
            "tokens": tokens,
        }
        self._is_dirty = True

    def add_nodes(self, nodes: list[TOCNode]) -> None:
        for node in nodes:
            self.add_node(node)

    def delete_node(self, node_id: str) -> None:
        if node_id in self._corpus:
            del self._corpus[node_id]
            self._is_dirty = True

    def delete_nodes(self, node_ids: list[str]) -> None:
        for nid in node_ids:
            self.delete_node(nid)

    def update_node_metadata(self, old_id: str, new_node: TOCNode) -> None:
        if old_id in self._corpus:
            del self._corpus[old_id]
        self.add_node(new_node)

    def _rebuild_index_if_needed(self) -> None:
        if self._is_dirty:
            self._node_id_list = list(self._corpus.keys())
            tokenized_corpus = [self._corpus[nid]["tokens"] for nid in self._node_id_list]
            if tokenized_corpus:
                self._bm25 = BM25Okapi(tokenized_corpus)
            else:
                self._bm25 = None
            self._is_dirty = False

    def search(self, query: str, top_k: int = 10) -> dict[str, float]:
        """Search BM25 and return a dict of {node_id: normalized_bm25_score}."""
        self._rebuild_index_if_needed()
        if not self._bm25 or not self._node_id_list:
            return {}

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return {}

        raw_scores = self._bm25.get_scores(query_tokens)
        max_score = float(max(raw_scores)) if len(raw_scores) > 0 else 0.0
        min_score = float(min(raw_scores)) if len(raw_scores) > 0 else 0.0

        score_range = max_score - min_score
        normalized_scores: dict[str, float] = {}

        for nid, raw in zip(self._node_id_list, raw_scores):
            if raw > 0.0:
                norm = (raw - min_score) / (score_range + 1e-9) if score_range > 0 else 1.0
                normalized_scores[nid] = float(norm)

        # Sort and take top_k
        sorted_items = sorted(
            normalized_scores.items(), key=lambda item: item[1], reverse=True
        )[:top_k]
        return dict(sorted_items)

    def get_node(self, node_id: str) -> Optional[TOCNode]:
        entry = self._corpus.get(node_id)
        return entry["node"] if entry else None

    def __len__(self) -> int:
        return len(self._corpus)

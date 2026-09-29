from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from arvan_project.config import settings
from arvan_project.parser.models import TOCNode, MarkdownDocument, DiffResult
from arvan_project.parser.tree_diff import TreeDiffEngine
from arvan_project.storage.base import BaseVectorStore, SearchResult
from arvan_project.storage.chroma_store import ChromaVectorStore
from arvan_project.storage.bm25_index import BM25Index


class HybridSearchStore:
    """Combines ChromaDB dense semantic vector search and BM25 lexical search.

    Implements:
    Score(d) = alpha * DenseScore(d) + (1 - alpha) * BM25Score(d)
    where alpha in [0.0, 1.0].
    """

    def __init__(
        self,
        vector_store: Optional[BaseVectorStore] = None,
        bm25_index: Optional[BM25Index] = None,
        registry_path: Optional[str] = None,
    ) -> None:
        self.vector_store = vector_store or ChromaVectorStore()
        self.bm25_index = bm25_index or BM25Index()
        self.registry_path = Path(registry_path or settings.doc_registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        # In-memory document registry mapping doc_id -> MarkdownDocument
        self._registry: dict[str, MarkdownDocument] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load stored document trees from disk."""
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                for doc_id, doc_dict in data.items():
                    doc = MarkdownDocument.model_validate(doc_dict)
                    self._registry[doc_id] = doc
                    # Populate BM25 index from stored registry
                    for node in doc.all_nodes():
                        if node.content.strip():
                            self.bm25_index.add_node(node)
            except Exception:
                pass

    def _save_registry(self) -> None:
        """Persist document registry to disk."""
        try:
            data = {doc_id: doc.model_dump() for doc_id, doc in self._registry.items()}
            self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get_document(self, doc_id: str) -> Optional[MarkdownDocument]:
        return self._registry.get(doc_id)

    def list_documents(self) -> list[str]:
        return list(self._registry.keys())

    def ingest_document(self, new_doc: MarkdownDocument) -> DiffResult:
        """Ingests a document using incremental diffing.

        Only embeds new or modified nodes, while preserving unchanged nodes.
        """
        old_doc = self._registry.get(new_doc.doc_id)
        diff = TreeDiffEngine.compute_diff(old_doc, new_doc)

        # 1. Process deletions
        if diff.node_ids_to_delete:
            self.vector_store.delete_nodes(diff.node_ids_to_delete)
            self.bm25_index.delete_nodes(diff.node_ids_to_delete)

        # 2. Process moved or renamed nodes (metadata update only, no embedding needed!)
        for old_node, new_node in diff.renamed_or_moved:
            self.vector_store.update_node_metadata(
                old_id=old_node.id,
                new_id=new_node.id,
                new_path_str=new_node.path_str,
                new_title=new_node.title,
            )
            self.bm25_index.update_node_metadata(old_node.id, new_node)

        # 3. Process new and modified nodes (requires embedding)
        nodes_to_embed = diff.nodes_needing_embedding
        if nodes_to_embed:
            self.vector_store.add_nodes(nodes_to_embed)
            self.bm25_index.add_nodes(nodes_to_embed)

        # 4. Update and persist registry
        self._registry[new_doc.doc_id] = new_doc
        self._save_registry()

        return diff

    def delete_document(self, doc_id: str) -> bool:
        """Deletes an entire document and its nodes from both indices."""
        doc = self._registry.get(doc_id)
        if not doc:
            return False

        node_ids = [n.id for n in doc.all_nodes()]
        self.vector_store.delete_nodes(node_ids)
        self.bm25_index.delete_nodes(node_ids)
        del self._registry[doc_id]
        self._save_registry()
        return True

    def search(
        self,
        query: str,
        alpha: Optional[float] = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Perform hybrid search combining dense semantic search and BM25 lexical search.

        alpha: Weight for dense vector search (0.0 = pure BM25, 1.0 = pure dense).
        """
        if alpha is None:
            alpha = settings.default_alpha

        # Clamp alpha to [0.0, 1.0]
        alpha = max(0.0, min(1.0, float(alpha)))

        # Candidate pool size
        candidate_k = max(top_k * 3, 10)

        # 1. Fetch dense candidates (if alpha > 0.0)
        dense_results: dict[str, SearchResult] = {}
        if alpha > 0.0:
            raw_dense = self.vector_store.search_dense(query, top_k=candidate_k)
            for r in raw_dense:
                dense_results[r.node_id] = r

        # 2. Fetch BM25 candidates (if alpha < 1.0)
        bm25_scores: dict[str, float] = {}
        if alpha < 1.0:
            bm25_scores = self.bm25_index.search(query, top_k=candidate_k)

        # 3. Merge candidates
        all_node_ids = set(dense_results.keys()).union(set(bm25_scores.keys()))
        if not all_node_ids:
            return []

        scored_results: list[SearchResult] = []

        for nid in all_node_ids:
            d_res = dense_results.get(nid)
            bm25_score = bm25_scores.get(nid, 0.0)
            dense_score = d_res.dense_score if d_res is not None and d_res.dense_score is not None else 0.0

            # Calculate hybrid score
            hybrid_score = (alpha * dense_score) + ((1.0 - alpha) * bm25_score)

            if d_res is not None:
                d_res.score = hybrid_score
                d_res.bm25_score = bm25_score
                scored_results.append(d_res)
            else:
                # Node matched by BM25 only
                node = self.bm25_index.get_node(nid)
                if node:
                    scored_results.append(
                        SearchResult(
                            doc_id=node.doc_id,
                            node_id=node.id,
                            title=node.title,
                            path_str=node.path_str,
                            content=node.get_embeddable_text(),
                            score=hybrid_score,
                            dense_score=dense_score,
                            bm25_score=bm25_score,
                            line_start=node.line_start,
                            line_end=node.line_end,
                            url=node.url,
                        )
                    )

        # Sort descending by hybrid score
        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:top_k]

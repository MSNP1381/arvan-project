from __future__ import annotations
from typing import Optional
from arvan_project.parser.models import TOCNode, MarkdownDocument, DiffResult


class TreeDiffEngine:
    """Computes incremental structural diffs between two versions of a document tree.

    Detects:
    - Unchanged nodes (content hash match at same path) -> Skip re-embedding
    - Modified nodes (path exists, content hash changed) -> Re-embed this node only
    - Added nodes (new path) -> Embed and insert
    - Deleted nodes (path removed) -> Delete vector and BM25 entries
    - Moved/Renamed nodes (same content hash, different path) -> Update metadata only
    """

    @classmethod
    def compute_diff(
        cls,
        old_doc: Optional[MarkdownDocument],
        new_doc: MarkdownDocument,
    ) -> DiffResult:
        doc_id = new_doc.doc_id

        if old_doc is None:
            # Entire document is new
            return DiffResult(
                doc_id=doc_id,
                added=new_doc.all_nodes(),
                unchanged=[],
                modified=[],
                deleted=[],
                renamed_or_moved=[],
            )

        old_nodes = old_doc.all_nodes()
        new_nodes = new_doc.all_nodes()

        old_by_path: dict[str, TOCNode] = {n.path_str: n for n in old_nodes}
        new_by_path: dict[str, TOCNode] = {n.path_str: n for n in new_nodes}

        unchanged: list[TOCNode] = []
        modified: list[tuple[TOCNode, TOCNode]] = []
        added_candidates: list[TOCNode] = []
        deleted_candidates: list[TOCNode] = []

        # Check nodes that exist in both paths
        for path_str, new_node in new_by_path.items():
            if path_str in old_by_path:
                old_node = old_by_path[path_str]
                if old_node.content_hash == new_node.content_hash:
                    unchanged.append(new_node)
                else:
                    modified.append((old_node, new_node))
            else:
                added_candidates.append(new_node)

        for path_str, old_node in old_by_path.items():
            if path_str not in new_by_path:
                deleted_candidates.append(old_node)

        # Detect moves / renames (same content hash, different path)
        renamed_or_moved: list[tuple[TOCNode, TOCNode]] = []
        final_added: list[TOCNode] = []
        unmatched_deleted: list[TOCNode] = list(deleted_candidates)

        for new_candidate in added_candidates:
            # Check if there is an unmatched deleted node with the same content hash
            matched_old = None
            if new_candidate.content_hash:
                for del_node in unmatched_deleted:
                    if del_node.content_hash == new_candidate.content_hash:
                        matched_old = del_node
                        break

            if matched_old:
                renamed_or_moved.append((matched_old, new_candidate))
                unmatched_deleted.remove(matched_old)
            else:
                final_added.append(new_candidate)

        return DiffResult(
            doc_id=doc_id,
            unchanged=unchanged,
            added=final_added,
            modified=modified,
            deleted=unmatched_deleted,
            renamed_or_moved=renamed_or_moved,
        )

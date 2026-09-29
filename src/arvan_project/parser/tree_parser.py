from __future__ import annotations
import re
from pathlib import Path
from typing import Optional
from arvan_project.parser.models import TOCNode, MarkdownDocument, compute_sha256


def extract_frontmatter(text: str) -> tuple[dict[str, str], str, int]:
    """Extract YAML frontmatter if present at the start of the document.

    Returns: (metadata_dict, remaining_text, line_offset)
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, 0

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, text, 0

    metadata: dict[str, str] = {}
    for line in lines[1:end_idx]:
        stripped = line.strip()
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            clean_key = key.strip()
            clean_val = val.strip().strip('"').strip("'")
            metadata[clean_key] = clean_val

    remaining_lines = lines[end_idx + 1 :]
    remaining_text = "\n".join(remaining_lines)
    return metadata, remaining_text, end_idx + 1


class MarkdownTreeParser:
    """Parses Markdown text into a hierarchical Table of Contents (TOC) tree.

    Properly respects code fences so that `#` comments inside code blocks
    are not falsely interpreted as headings. Also handles YAML frontmatter.
    """

    HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.*)$")

    def __init__(self, default_doc_id: Optional[str] = None):
        self.default_doc_id = default_doc_id

    def parse_file(self, file_path: str | Path, doc_id: Optional[str] = None) -> MarkdownDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")
        text = path.read_text(encoding="utf-8")
        doc_id = doc_id or path.stem
        return self.parse_text(text, doc_id=doc_id, title=path.name)

    def parse_text(
        self, text: str, doc_id: Optional[str] = None, title: Optional[str] = None
    ) -> MarkdownDocument:
        doc_id = doc_id or self.default_doc_id or "doc"

        # Extract YAML frontmatter if present
        meta, content_text, line_offset = extract_frontmatter(text)
        doc_url = meta.get("url", "")
        doc_desc = meta.get("description", "")
        frontmatter_title = meta.get("title", "")

        lines = content_text.splitlines()

        # Step 1: Slice text into sections delimited by headings (ignoring code fences)
        in_code_block = False
        raw_sections: list[dict] = []
        current_title: Optional[str] = None
        current_level: int = 0
        current_lines: list[str] = []
        current_start: int = 1

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Toggle code fence
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            if not in_code_block and stripped.startswith("#"):
                match = self.HEADING_REGEX.match(stripped)
                if match:
                    # Previous section ends at line_idx - 1
                    if current_title is not None or any(l.strip() for l in current_lines):
                        raw_sections.append(
                            {
                                "title": current_title or "Overview",
                                "level": current_level or 1,
                                "lines": current_lines,
                                "line_start": current_start,
                                "line_end": line_idx - 1,
                            }
                        )
                    current_level = len(match.group(1))
                    current_title = match.group(2).strip()
                    current_lines = []
                    current_start = line_idx
                    continue

            current_lines.append(line)

        # Flush the final section
        if current_title is not None or any(l.strip() for l in current_lines):
            raw_sections.append(
                {
                    "title": current_title or "Overview",
                    "level": current_level or 1,
                    "lines": current_lines,
                    "line_start": current_start,
                    "line_end": len(lines),
                }
            )

        # Step 2: Build hierarchical tree from raw sections using a stack
        root_nodes: list[TOCNode] = []
        stack: list[TOCNode] = []
        doc_title = title or (root_nodes[0].title if root_nodes else doc_id)

        for sec in raw_sections:
            sec_title = sec["title"]
            sec_level = sec["level"]
            sec_content = "\n".join(sec["lines"]).strip()
            line_start = sec["line_start"] + line_offset
            line_end = sec["line_end"] + line_offset

            # Pop stack while top has level >= sec_level
            while stack and stack[-1].level >= sec_level:
                stack.pop()

            if not stack:
                # Top-level node
                path = [sec_title]
                node_id = f"{doc_id}::{sec_title}"
                node = TOCNode(
                    id=node_id,
                    doc_id=doc_id,
                    title=sec_title,
                    level=sec_level,
                    path=path,
                    path_str=sec_title,
                    content=sec_content,
                    content_hash=compute_sha256(sec_content),
                    line_start=line_start,
                    line_end=line_end,
                    children=[],
                    is_leaf=True,
                    url=doc_url,
                )
                root_nodes.append(node)
                stack.append(node)
            else:
                parent = stack[-1]
                parent.is_leaf = False
                path = parent.path + [sec_title]
                path_str = " > ".join(path)
                node_id = f"{doc_id}::{path_str}"
                node = TOCNode(
                    id=node_id,
                    doc_id=doc_id,
                    title=sec_title,
                    level=sec_level,
                    path=path,
                    path_str=path_str,
                    content=sec_content,
                    content_hash=compute_sha256(sec_content),
                    line_start=line_start,
                    line_end=line_end,
                    children=[],
                    is_leaf=True,
                    url=doc_url,
                )
                parent.children.append(node)
                stack.append(node)

        # Determine document title: explicit title, or frontmatter_title, or first H1 root, or doc_id
        if title and not title.endswith(".md"):
            doc_title = title
        elif frontmatter_title:
            doc_title = frontmatter_title
        elif root_nodes and root_nodes[0].level == 1:
            doc_title = root_nodes[0].title
        else:
            doc_title = title or doc_id

        return MarkdownDocument(
            doc_id=doc_id,
            title=doc_title,
            url=doc_url,
            description=doc_desc,
            raw_content=text,
            root_nodes=root_nodes,
            content_hash=compute_sha256(text),
        )

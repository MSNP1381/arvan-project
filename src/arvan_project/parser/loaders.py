from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from arvan_project.parser.models import TOCNode, MarkdownDocument
from arvan_project.parser.tree_parser import MarkdownTreeParser


class UniversalDocumentLoader:
    """Universal document ingestion loader supporting Markdown, Text, and PDF.

    - Markdown (.md): Uses the custom MarkdownTreeParser to generate hierarchical
      AST trees based on ATX headings (H1-H6), code comment protection, and line spans.
    - PDF (.pdf): Uses LangChain's official PyPDFLoader with RecursiveCharacterTextSplitter.
    - Text (.txt): Uses LangChain's official TextLoader with RecursiveCharacterTextSplitter.

    All formats output a unified MarkdownDocument with TOCNode chunks, allowing
    seamless incremental SHA-256 diffing and hybrid (ChromaDB + BM25) retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.markdown_parser = MarkdownTreeParser()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
        )

    def load_file(self, file_path: str | Path, doc_id: Optional[str] = None) -> MarkdownDocument:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        clean_id = doc_id or path.stem
        suffix = path.suffix.lower()

        if suffix in (".md", ".markdown"):
            return self.markdown_parser.parse_file(path, doc_id=clean_id)
        elif suffix == ".pdf":
            return self._load_pdf(path, clean_id)
        elif suffix in (".txt", ".text", ".log"):
            return self._load_text(path, clean_id)
        else:
            # Fallback to TextLoader for unknown text-like extensions
            return self._load_text(path, clean_id)

    def _load_pdf(self, path: Path, doc_id: str) -> MarkdownDocument:
        """Load PDF using LangChain's PyPDFLoader and split into TOCNode chunks."""
        loader = PyPDFLoader(str(path))
        raw_docs = loader.load()

        if not raw_docs:
            return MarkdownDocument(
                doc_id=doc_id,
                title=doc_id,
                raw_content="",
                root_nodes=[],
            )

        chunks = self.text_splitter.split_documents(raw_docs)
        doc_title = path.stem.replace("_", " ").replace("-", " ").title()

        root_node = TOCNode(
            id=f"{doc_id}#root",
            doc_id=doc_id,
            title=doc_title,
            level=1,
            path=[doc_title],
            content="",
            line_start=1,
            line_end=len(raw_docs),
            is_leaf=False,
            children=[],
        )

        all_text_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            page_num = chunk.metadata.get("page", 0) + 1  # 1-indexed page
            chunk_text = chunk.page_content.strip()
            if not chunk_text:
                continue

            all_text_parts.append(chunk_text)
            page_title = f"Page {page_num} (Part {idx})"
            child_node = TOCNode(
                id=f"{doc_id}#p{page_num}_c{idx}",
                doc_id=doc_id,
                title=page_title,
                level=2,
                path=[doc_title, f"Page {page_num}"],
                content=chunk_text,
                line_start=page_num,
                line_end=page_num,
                is_leaf=True,
            )
            root_node.children.append(child_node)

        return MarkdownDocument(
            doc_id=doc_id,
            title=doc_title,
            raw_content="\n\n".join(all_text_parts),
            root_nodes=[root_node],
        )

    def _load_text(self, path: Path, doc_id: str) -> MarkdownDocument:
        """Load Text file using LangChain's TextLoader and split into TOCNode chunks."""
        loader = TextLoader(str(path), encoding="utf-8")
        raw_docs = loader.load()

        if not raw_docs:
            return MarkdownDocument(
                doc_id=doc_id,
                title=doc_id,
                raw_content="",
                root_nodes=[],
            )

        chunks = self.text_splitter.split_documents(raw_docs)
        doc_title = path.stem.replace("_", " ").replace("-", " ").title()

        root_node = TOCNode(
            id=f"{doc_id}#root",
            doc_id=doc_id,
            title=doc_title,
            level=1,
            path=[doc_title],
            content="",
            line_start=1,
            line_end=len(chunks),
            is_leaf=False,
            children=[],
        )

        all_text_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            chunk_text = chunk.page_content.strip()
            if not chunk_text:
                continue

            all_text_parts.append(chunk_text)
            section_title = f"Section {idx}"
            child_node = TOCNode(
                id=f"{doc_id}#sec_{idx}",
                doc_id=doc_id,
                title=section_title,
                level=2,
                path=[doc_title, section_title],
                content=chunk_text,
                line_start=idx,
                line_end=idx,
                is_leaf=True,
            )
            root_node.children.append(child_node)

        return MarkdownDocument(
            doc_id=doc_id,
            title=doc_title,
            raw_content="\n\n".join(all_text_parts),
            root_nodes=[root_node],
        )

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Any
import chromadb
from chromadb.api.models.Collection import Collection

from arvan_project.config import settings
from arvan_project.parser.models import TOCNode
from arvan_project.storage.base import BaseVectorStore, SearchResult


from chromadb import EmbeddingFunction, Documents, Embeddings
from tqdm import tqdm


class SimpleHashEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic fallback embedding for testing / offline demo when API key is unset."""

    def __init__(self) -> None:
        super().__init__()

    def name(self) -> str:
        return "simple_hash_embedding"

    def get_config(self) -> dict[str, Any]:
        return {}

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            # Deterministic pseudo-embedding of length 128
            vec = [0.0] * 128
            for i, word in enumerate(text.lower().split()):
                idx = hash(word) % 128
                vec[idx] += 1.0 / (i + 1)
            # Normalize
            norm = sum(x**2 for x in vec) ** 0.5
            if norm > 0:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


class GoogleGenAIEmbeddingAdapter(EmbeddingFunction[Documents]):
    """Adapter for langchain-google-genai GoogleGenerativeAIEmbeddings with resilient offline fallback."""

    def __init__(self, emb_model: Any, fallback_fn: Optional[Any] = None) -> None:
        super().__init__()
        self.emb_model = emb_model
        self.fallback_fn = fallback_fn or SimpleHashEmbeddingFunction()

    def name(self) -> str:
        return "google_genai_embedding"

    def get_config(self) -> dict[str, Any]:
        return {}

    def __call__(self, input: Documents) -> Embeddings:
        try:
            return self.emb_model.embed_documents(input)
        except Exception as e:
            print(f"[Warning: Google Embedding API call failed ({e}); using local fallback embedding]")
            return self.fallback_fn(input)


class ArvanAIEmbeddingAdapter(EmbeddingFunction[Documents]):
    """Embedding adapter for Arvan Cloud AI's OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "Gemini-embedding-001",
        fallback_fn: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.fallback_fn = fallback_fn or SimpleHashEmbeddingFunction()

    def name(self) -> str:
        return f"arvan_ai_{self.model}"

    def get_config(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "model": self.model,
        }

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        import requests
        import time

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=90)
                resp.raise_for_status()
                data = resp.json()
                sorted_data = sorted(data["data"], key=lambda item: item.get("index", 0))
                return [item["embedding"] for item in sorted_data]
            except Exception as ex:
                if attempt == 2:
                    raise ex
                time.sleep(1.0 * (attempt + 1))
        return []

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []
        try:
            batch_size = 16
            all_embeddings = []
            chunks = [input[i : i + batch_size] for i in range(0, len(input), batch_size)]
            if len(chunks) > 1:
                with tqdm(chunks, desc="  -> Embedding batches", unit="batch", leave=False, dynamic_ncols=True) as pbar:
                    for chunk in pbar:
                        chunk_embeddings = self._embed_batch(chunk)
                        all_embeddings.extend(chunk_embeddings)
            else:
                for chunk in chunks:
                    chunk_embeddings = self._embed_batch(chunk)
                    all_embeddings.extend(chunk_embeddings)
            return all_embeddings
        except Exception as e:
            print(f"[Warning: Arvan AI Embedding API call failed ({e}); using local fallback embedding]")
            return self.fallback_fn(input)


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation of BaseVectorStore for TOC tree leaves."""

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "markdown_sections",
        embedding_fn: Optional[Any] = None,
    ) -> None:
        self.persist_directory = persist_directory or settings.chroma_persist_dir
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.embedding_fn = embedding_fn

        # Configure embedding function
        if self.embedding_fn is None:
            if settings.arvan_ai_base_url and settings.arvan_ai_api_key:
                self.embedding_fn = ArvanAIEmbeddingAdapter(
                    base_url=settings.arvan_ai_base_url,
                    api_key=settings.arvan_ai_api_key,
                    model=settings.embedding_model,
                )
            else:
                api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY")
                if api_key:
                    try:
                        from langchain_google_genai import GoogleGenerativeAIEmbeddings

                        genai_embeddings = GoogleGenerativeAIEmbeddings(
                            model=settings.embedding_model,
                            api_key=api_key,
                        )
                        self.embedding_fn = GoogleGenAIEmbeddingAdapter(genai_embeddings)
                    except Exception:
                        self.embedding_fn = SimpleHashEmbeddingFunction()
                else:
                    self.embedding_fn = SimpleHashEmbeddingFunction()

        self.collection: Collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_nodes(self, nodes: list[TOCNode]) -> None:
        """Upsert TOC nodes into ChromaDB."""
        valid_nodes = [n for n in nodes if n.content.strip()]
        if not valid_nodes:
            return

        ids = [n.id for n in valid_nodes]
        documents = [n.get_embeddable_text() for n in valid_nodes]
        metadatas = [
            {
                "doc_id": n.doc_id,
                "node_id": n.id,
                "title": n.title,
                "path_str": n.path_str,
                "content_hash": n.content_hash,
                "line_start": n.line_start,
                "line_end": n.line_end,
                "level": n.level,
                "url": getattr(n, "url", ""),
            }
            for n in valid_nodes
        ]

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def delete_nodes(self, node_ids: list[str]) -> None:
        """Remove nodes by ID."""
        if not node_ids:
            return
        # Chroma raises error if ids don't exist, so query first or wrap in try
        try:
            self.collection.delete(ids=node_ids)
        except Exception:
            pass

    def update_node_metadata(
        self, old_id: str, new_id: str, new_path_str: str, new_title: str
    ) -> None:
        """Update node metadata without re-embedding."""
        try:
            res = self.collection.get(ids=[old_id], include=["embeddings", "documents", "metadatas"])
            if res and res["ids"]:
                emb = res["embeddings"][0] if res.get("embeddings") is not None else None
                doc = res["documents"][0] if res.get("documents") else ""
                meta = res["metadatas"][0] if res.get("metadatas") else {}

                meta["node_id"] = new_id
                meta["path_str"] = new_path_str
                meta["title"] = new_title

                # Insert with new ID
                if emb is not None:
                    self.collection.upsert(
                        ids=[new_id],
                        embeddings=[emb],
                        documents=[doc],
                        metadatas=[meta],
                    )
                else:
                    self.collection.upsert(
                        ids=[new_id],
                        documents=[doc],
                        metadatas=[meta],
                    )
                # Delete old
                if old_id != new_id:
                    self.collection.delete(ids=[old_id])
        except Exception:
            pass

    def search_dense(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Perform dense semantic search."""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for nid, doc, meta, dist in zip(ids, docs, metas, distances):
            # Chroma with cosine distance: distance = 1 - cosine_similarity
            # similarity = 1 - distance
            dense_similarity = max(0.0, 1.0 - float(dist))

            search_results.append(
                SearchResult(
                    doc_id=str(meta.get("doc_id", "")),
                    node_id=nid,
                    title=str(meta.get("title", "")),
                    path_str=str(meta.get("path_str", "")),
                    content=doc,
                    score=dense_similarity,
                    dense_score=dense_similarity,
                    bm25_score=None,
                    line_start=int(meta.get("line_start", 0)),
                    line_end=int(meta.get("line_end", 0)),
                    url=str(meta.get("url", "")),
                )
            )

        return search_results

from __future__ import annotations
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from pydantic import BaseModel, Field

from arvan_project.config import settings
from arvan_project.parser.loaders import UniversalDocumentLoader
from arvan_project.storage.hybrid_store import HybridSearchStore
from arvan_project.storage.base import SearchResult
from arvan_project.agent.tools import set_store, calculate_server_price as calc_price_tool
from arvan_project.agent.graph import create_agent_graph
from arvan_project.calculator import calculate_server_cost


# Shared app state
_store: Optional[HybridSearchStore] = None
_agent_graph: Any = None
_loader: Optional[UniversalDocumentLoader] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _agent_graph, _loader
    _store = HybridSearchStore()
    set_store(_store)
    _loader = UniversalDocumentLoader()
    try:
        _agent_graph = create_agent_graph()
    except Exception:
        _agent_graph = None
    yield


app = FastAPI(
    title="Arvan Cloud Agentic RAG API",
    description=(
        "Production-ready Agentic Retrieval-Augmented Generation (RAG) API for Arvan Cloud Server documentation.\n\n"
        "Features:\n"
        "- **Multi-format Support**: Markdown (AST Tree & Breadcrumbs), PDF (PyPDFLoader), and Text.\n"
        "- **Zero-Token Invariant**: Incremental SHA-256 diffing preserves unchanged sections without embedding cost.\n"
        "- **Hybrid Fusion Search**: ChromaDB (Dense) + BM25Okapi (Lexical) with configurable alpha weighting.\n"
        "- **Document Change Management**: Full addition, modification, and complete deletion.\n"
        "- **Cloud Server Pricing**: Exact hourly and monthly calculations in Tomans (تومان)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for browser integration and Swagger UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request / Response Models
# ============================================================================

class CitationModel(BaseModel):
    doc_id: str = Field(description="Document ID")
    title: str = Field(description="Section heading or title")
    path_str: str = Field(description="Hierarchical breadcrumb path")
    citation: str = Field(description="Formatted traceable citation")
    score: float = Field(description="Hybrid fusion score")
    dense_score: Optional[float] = Field(default=None, description="Normalized dense cosine score")
    bm25_score: Optional[float] = Field(default=None, description="Normalized BM25 score")
    line_start: int = Field(default=0, description="Starting line or page number")
    line_end: int = Field(default=0, description="Ending line or page number")
    snippet: str = Field(description="Preview of matched text content")


class QueryRequest(BaseModel):
    query: str = Field(..., description="User query / question", min_length=1)
    alpha: float = Field(
        default=0.8,
        description="Hybrid fusion weight (0.0 = pure BM25, 1.0 = pure Dense vector, 0.8 = balanced)",
        ge=0.0,
        le=1.0,
    )
    top_k: int = Field(default=4, description="Maximum number of context chunks to retrieve", ge=1, le=20)
    use_agent: bool = Field(
        default=True,
        description="Whether to run the multi-turn LangGraph Agent (with tools and synthesis) or fast direct hybrid RAG",
    )


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[CitationModel]
    used_tools: list[str]


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    alpha: float = Field(default=0.8, ge=0.0, le=1.0)
    top_k: int = Field(default=4, ge=1, le=20)


class DiffSummaryModel(BaseModel):
    unchanged_nodes: int
    newly_embedded_nodes: int
    modified_nodes: int
    deleted_nodes: int
    renamed_or_moved_nodes: int


class IngestResponse(BaseModel):
    doc_id: str
    title: str
    total_nodes: int
    diff_summary: DiffSummaryModel
    message: str


class DocumentSummaryModel(BaseModel):
    doc_id: str
    title: str
    total_nodes: int
    url: str


class PricingRequest(BaseModel):
    cpu_cores: float = Field(..., description="Number of CPU cores", ge=1)
    ram_gb: float = Field(..., description="RAM size in GB", ge=1)
    storage_gb: float = Field(..., description="Storage size in GB", ge=10)
    region: str = Field(default="iran", description="'iran' or 'europe'")
    tier: str = Field(default="standard", description="'basic', 'standard', or 'premium'")
    storage_type: str = Field(default="ssd", description="'ssd' or 'hdd'")
    download_traffic_gb: float = Field(default=0.0, ge=0)
    upload_traffic_gb: float = Field(default=0.0, ge=0)
    backup_gb: float = Field(default=0.0, ge=0)
    snapshot_gb: float = Field(default=0.0, ge=0)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/health", tags=["System"])
def health_check():
    """Health check endpoint indicating service state and indexed document count."""
    global _store
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    doc_count = len(_store.list_documents())
    return {
        "status": "healthy",
        "app": "Arvan Cloud Agentic RAG API",
        "indexed_documents": doc_count,
        "default_alpha": settings.default_alpha,
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }


@app.post("/api/query", response_model=QueryResponse, tags=["Retrieval & QA"])
def query_agent(req: QueryRequest):
    """Answers user queries with grounded citations based exclusively on indexed documentation.

    - Uses the LangGraph StateGraph agent equipped with `search_documentation`, `get_document_toc`,
      `calculate_server_price`, and `escalate_to_support`.
    - Returns traceable citations linking each assertion to document paths and line spans.
    - Explicitly declares when information is not present in documentation.
    """
    global _store, _agent_graph
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    # 1. Retrieve hybrid search results for citation extraction
    search_results = _store.search(query=req.query, alpha=req.alpha, top_k=req.top_k)
    citations: list[CitationModel] = []
    for r in search_results:
        citations.append(
            CitationModel(
                doc_id=r.doc_id,
                title=r.title,
                path_str=r.path_str,
                citation=r.format_citation(),
                score=round(r.score, 4),
                dense_score=round(r.dense_score, 4) if r.dense_score is not None else None,
                bm25_score=round(r.bm25_score, 4) if r.bm25_score is not None else None,
                line_start=r.line_start,
                line_end=r.line_end,
                snippet=r.content[:300] + ("..." if len(r.content) > 300 else ""),
            )
        )

    # 2. Invoke LangGraph agent if available
    used_tools: list[str] = []
    answer_text = ""

    if req.use_agent and _agent_graph is not None:
        try:
            state = {"messages": [HumanMessage(content=req.query)]}
            result_state = _agent_graph.invoke(state)
            messages = result_state.get("messages", [])

            for msg in messages:
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    for call in msg.tool_calls:
                        used_tools.append(call["name"])
                elif isinstance(msg, ToolMessage):
                    if msg.name and msg.name not in used_tools:
                        used_tools.append(msg.name)

            # Last non-tool AIMessage is final answer
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and not msg.tool_calls:
                    content = msg.content
                    if isinstance(content, list):
                        parts = [item.get("text", "") if isinstance(item, dict) else str(item) for item in content]
                        answer_text = "".join(parts)
                    else:
                        answer_text = str(content)
                    break
        except Exception as e:
            # Fallback if external API key is offline
            answer_text = ""

    # 3. Fallback direct synthesis if agent offline or disabled
    if not answer_text:
        if not citations:
            answer_text = (
                "اطلاعات کافی درباره این پرسش در مستندات پایگاه دانش ابر آروان یافت نشد. "
                "جهت اطمینان از تولید پاسخ‌های دقیق، از پاسخ‌دهی بدون پشتوانه خودداری می‌شود."
            )
        else:
            top_cite = citations[0]
            answer_text = (
                f"بر اساس مستندات پایگاه دانش ابر آروان:\n\n"
                f"**ارجاع:** `{top_cite.citation}`\n\n"
                f"{top_cite.snippet}\n\n"
                f"جهت مشاهده کامل به بخش مربوطه مراجعه فرمایید."
            )

    return QueryResponse(
        query=req.query,
        answer=answer_text,
        citations=citations,
        used_tools=used_tools,
    )


@app.post("/api/search", response_model=list[CitationModel], tags=["Retrieval & QA"])
def hybrid_search(req: SearchRequest):
    """Performs raw hybrid search (Dense + BM25) and returns ranked section matches with scoring."""
    global _store
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    results = _store.search(query=req.query, alpha=req.alpha, top_k=req.top_k)
    return [
        CitationModel(
            doc_id=r.doc_id,
            title=r.title,
            path_str=r.path_str,
            citation=r.format_citation(),
            score=round(r.score, 4),
            dense_score=round(r.dense_score, 4) if r.dense_score is not None else None,
            bm25_score=round(r.bm25_score, 4) if r.bm25_score is not None else None,
            line_start=r.line_start,
            line_end=r.line_end,
            snippet=r.content,
        )
        for r in results
    ]


@app.post("/api/documents/ingest", response_model=IngestResponse, tags=["Document Management"])
async def ingest_document(
    file: UploadFile = File(..., description="Document file (.md, .pdf, or .txt)"),
    doc_id: Optional[str] = Form(None, description="Optional custom document ID"),
):
    """Ingests a Markdown, PDF, or Plain Text document into the knowledge base.

    - Computes incremental SHA-256 diffing against previous versions.
    - Preserves unchanged sections with 0 API tokens.
    - Indexes into ChromaDB dense vectors and BM25 lexical index.
    """
    global _store, _loader
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)
    if _loader is None:
        _loader = UniversalDocumentLoader()

    filename = file.filename or "uploaded_document"
    clean_doc_id = doc_id or Path(filename).stem
    suffix = Path(filename).suffix.lower()

    if suffix not in (".md", ".markdown", ".pdf", ".txt", ".text"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{suffix}'. Allowed formats: .md, .pdf, .txt",
        )

    # Save to temporary file for loading
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        doc = _loader.load_file(tmp_path, doc_id=clean_doc_id)
        diff = _store.ingest_document(doc)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return IngestResponse(
        doc_id=doc.doc_id,
        title=doc.title,
        total_nodes=len(doc.all_nodes()),
        diff_summary=DiffSummaryModel(
            unchanged_nodes=len(diff.unchanged),
            newly_embedded_nodes=len(diff.nodes_needing_embedding),
            modified_nodes=len(diff.modified),
            deleted_nodes=len(diff.deleted),
            renamed_or_moved_nodes=len(diff.renamed_or_moved),
        ),
        message=f"Document '{doc.doc_id}' successfully ingested. Embedded {len(diff.nodes_needing_embedding)} nodes, preserved {len(diff.unchanged)} unchanged.",
    )


@app.get("/api/documents", response_model=list[DocumentSummaryModel], tags=["Document Management"])
def list_documents():
    """Lists all indexed documents currently stored in the knowledge base."""
    global _store
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    doc_ids = _store.list_documents()
    summaries = []
    for doc_id in doc_ids:
        doc = _store.get_document(doc_id)
        if doc:
            summaries.append(
                DocumentSummaryModel(
                    doc_id=doc.doc_id,
                    title=doc.title or doc.doc_id,
                    total_nodes=len(doc.all_nodes()),
                    url=doc.url,
                )
            )
    return summaries


@app.get("/api/documents/{doc_id}/toc", tags=["Document Management"])
def get_document_toc(doc_id: str):
    """Retrieves the hierarchical Table of Contents (TOC) structure of an indexed document."""
    global _store
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    doc = _store.get_document(doc_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    def serialize_node(node):
        return {
            "id": node.id,
            "title": node.title,
            "level": node.level,
            "path_str": node.path_str,
            "line_start": node.line_start,
            "line_end": node.line_end,
            "is_leaf": node.is_leaf,
            "children": [serialize_node(c) for c in node.children],
        }

    return {
        "doc_id": doc.doc_id,
        "title": doc.title,
        "root_nodes": [serialize_node(r) for r in doc.root_nodes],
    }


@app.delete("/api/documents/{doc_id}", tags=["Document Management"])
def delete_document(doc_id: str):
    """Deletes an entire document, purging all its embeddings from ChromaDB and terms from BM25.

    Ensures that outdated or removed documentation is never used as the basis for new answers.
    """
    global _store
    if _store is None:
        _store = HybridSearchStore()
        set_store(_store)

    success = _store.delete_document(doc_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    return {
        "doc_id": doc_id,
        "deleted": True,
        "message": f"Document '{doc_id}' and all associated vectors and lexical indices successfully purged.",
    }


@app.post("/api/calculator/price", tags=["Cloud Server Pricing"])
def calculate_price(req: PricingRequest):
    """Calculates official hourly and monthly costs for Arvan Cloud Server resources in Tomans."""
    cost = calculate_server_cost(
        cpu_cores=req.cpu_cores,
        ram_gb=req.ram_gb,
        storage_gb=req.storage_gb,
        region=req.region,
        tier=req.tier,
        storage_type=req.storage_type,
        download_traffic_gb=req.download_traffic_gb,
        upload_traffic_gb=req.upload_traffic_gb,
        backup_gb=req.backup_gb,
        snapshot_gb=req.snapshot_gb,
    )
    return {
        "total_hourly_toman": cost.total_hourly_toman,
        "total_monthly_toman": cost.total_monthly_toman,
        "breakdown": [
            {
                "name": item.name,
                "details": item.details,
                "hourly_toman": item.hourly_toman,
                "monthly_toman": item.monthly_toman,
            }
            for item in cost.items
        ],
        "formatted_summary": cost.format_persian_markdown(),
    }

# AGENTS.md

Instructions and technical guidelines for AI coding agents operating in this repository.

---

## 1. Project Context & Tech Stack

This project is an **Agentic Retrieval-Augmented Generation (RAG)** application designed for structured technical documentation.

- **Language & Runtime**: Python 3.12 / 3.13
- **Package & Environment Manager**: `uv` (Astral) — never use bare `pip` or system `python`.
- **Frameworks**:
  - `langgraph` & `langgraph-api`: State machine agent orchestration and Studio UI.
  - `langchain` & `langchain-core`: Abstractions, messages, and tool definitions.
  - `langchain-google-genai`: Gemini 3.8 / 2.0 Flash integration.
- **Embeddings & Vector Database**:
  - Primary Embeddings: **Arvan Cloud AI** (`Gemini-embedding-001`, 3072 dimensions) via OpenAI-compatible endpoint.
  - Vector Store: **ChromaDB** with persistent disk storage (`.chroma_data/`).
  - Lexical Search: `rank-bm25` (BM25Okapi).

---

## 2. Standard Commands & Workflows

Always execute commands through `uv run` inside the project directory:

| Task | Command |
| :--- | :--- |
| **Sync Dependencies** | `uv sync` |
| **Run Test Suite** | `uv run pytest -v` |
| **Run Single Test** | `uv run pytest tests/test_diff.py -v` |
| **Validate LangGraph Config** | `uv run langgraph validate` |
| **Start Studio Dev Server** | `$env:PYTHONIOENCODING="utf-8"; uv run langgraph dev --no-browser --port 2024` |
| **CLI: Ingest Document** | `uv run python -m arvan_project.cli ingest docs/sample_architecture.md` |
| **CLI: Inspect TOC Tree** | `uv run python -m arvan_project.cli toc sample_architecture` |
| **CLI: Hybrid Search** | `uv run python -m arvan_project.cli search "<query>" --alpha 0.5` |
| **CLI: Interactive Chat** | `uv run python -m arvan_project.cli chat` |

---

## 3. Repository Architecture & Code Map

```
src/arvan_project/
├── config.py             # Pydantic Settings (loads .env, models, paths, defaults)
├── cli.py                # Rich terminal CLI commands (ingest, toc, search, chat)
├── parser/
│   ├── models.py         # TOCNode, DiffResult, MarkdownDocument data models
│   ├── tree_parser.py    # CommonMark AST parser; extracts ATX headings into TOC tree
│   └── tree_diff.py      # Incremental SHA-256 diff engine (detects unchanged/added/modified/deleted)
├── storage/
│   ├── base.py           # BaseVectorStore interface and SearchResult model
│   ├── chroma_store.py   # ChromaDB wrapper + ArvanAIEmbeddingAdapter (multithreaded batching)
│   ├── bm25_index.py     # BM25Okapi inverted index with incremental update support
│   └── hybrid_store.py   # Hybrid fusion search (Score = α · Dense + (1 - α) · BM25)
└── agent/
    ├── prompts.py        # System prompts for agent router, grader, synthesizer
    ├── tools.py          # LangChain @tool definitions (search_documentation, get_document_toc, read_section)
    ├── state.py          # AgentState TypedDict (must have total=False for Studio compatibility)
    └── graph.py          # LangGraph StateGraph compilation (exports `graph`)
```

---

## 4. Invariant Rules (DO NOT BREAK)

1. **Breadcrumb Context in Embeddings**:
   Every embedded chunk must prepend its full hierarchical breadcrumb path:
   ```text
   Section: [Document Title > Section > Subsection]

   [Content body]
   ```
   Never embed isolated raw paragraphs without their breadcrumb header.

2. **Zero-Token Unchanged Node Invariant**:
   In `TreeDiffEngine`, whenever a document is re-ingested:
   - Nodes whose SHA-256 content hashes match MUST be classified as `unchanged`.
   - Never call embedding APIs for `unchanged` nodes.

3. **Renamed / Moved Heading Optimization**:
   If a heading title changes but its content hash is identical to an old node:
   - Classify as `renamed_or_moved`.
   - Update metadata in ChromaDB and BM25 directly.
   - Do NOT re-embed or waste embedding tokens.

4. **Code Block Comment Protection**:
   Lines starting with `#` inside fenced code blocks (````` ```python ... ``` `````) are code comments, **NOT** Markdown headings. `MarkdownTreeParser` must always maintain code block fence tracking.

5. **Score Normalization for Hybrid Search**:
   BM25 scores are unbounded $[0, \infty)$, while dense cosine similarity is in $[0, 1]$.
   Always MinMax normalize both scores before applying the weighted sum:
   $$\text{Score}(d) = \alpha \cdot \text{DenseNorm}(d) + (1 - \alpha) \cdot \text{BM25Norm}(d)$$

6. **Offline Fallback Guarantee**:
   `ChromaVectorStore` must always maintain `SimpleHashEmbeddingFunction` as a fallback so that unit tests, local verification, and CI/CD never fail if network or API keys are unavailable.

7. **LangGraph Studio State Compatibility**:
   `AgentState` in `src/arvan_project/agent/state.py` must use `total=False`. LangGraph Studio passes `{"messages": [...]}` alone when starting a chat thread.

---

## 5. Protected Boundaries & Security

- **Never Commit or Overwrite `.env`**: Contains sensitive API keys (`ARVAN_AI_API_KEY`, `GOOGLE_API_KEY`).
- **Never Manually Edit `.chroma_data/`**: Managed exclusively by ChromaDB and `HybridSearchStore`.
- **Never Modify `.venv/` Directly**: Use `uv add` or `uv sync` to manage dependencies.
- **Windows Console Encoding**: Click/Rich emojis may trigger `cp1252` encoding errors on Windows. When starting servers or testing commands, always ensure `$env:PYTHONIOENCODING="utf-8"` is set.

---

## 6. Verification Checklist for Agents

Before completing any task in this codebase:
- [ ] Run `uv run pytest -v` and ensure all tests pass (0 failures).
- [ ] Run `uv run langgraph validate` if any graph, agent, or dependency changes were made.
- [ ] If changing parser logic, verify code fences and deep headings (`H1`-`H6`).
- [ ] If changing storage logic, verify incremental diffing requires 0 embeddings on identical re-ingestion.

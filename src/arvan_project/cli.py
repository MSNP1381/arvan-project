from __future__ import annotations
import sys
import argparse
from typing import Any
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.markdown import Markdown
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from tqdm import tqdm

from arvan_project.parser.tree_parser import MarkdownTreeParser
from arvan_project.parser.models import TOCNode
from arvan_project.storage.hybrid_store import HybridSearchStore
from arvan_project.agent.tools import set_store
from arvan_project.agent.graph import create_agent_graph

# Ensure UTF-8 output across Windows environments
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def print_toc_tree(node: TOCNode, tree: Tree) -> None:
    leaf_str = "[cyan](leaf)[/cyan]" if node.is_leaf else "[dim](branch)[/dim]"
    branch = tree.add(
        f"[bold]{node.title}[/bold] [dim]H{node.level} (lines {node.line_start}-{node.line_end})[/dim] {leaf_str}"
    )
    for child in node.children:
        print_toc_tree(child, branch)


def handle_ingest(file_path: str, doc_id: str | None = None) -> None:
    path = Path(file_path)
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] File or directory not found: {file_path}")
        sys.exit(1)

    store = HybridSearchStore()
    set_store(store)
    parser = MarkdownTreeParser()

    if path.is_dir():
        # Directory ingestion mode
        md_files = sorted(
            [f for f in path.rglob("*.md") if f.name != "SUMMARY.md"]
        )
        if not md_files:
            console.print(f"[yellow]No .md files found in directory: {file_path}[/yellow]")
            return

        console.print(
            Panel(
                f"[bold green]Starting Batch Ingestion of {len(md_files)} documents from:[/bold green] [cyan]{file_path}[/cyan]",
                title="Arvan Cloud Documentation Ingestion",
            )
        )

        overall_table = Table(title="Batch Ingestion Results")
        overall_table.add_column("Doc ID", style="cyan")
        overall_table.add_column("Title", style="bold")
        overall_table.add_column("Preserved (0 Tokens)", justify="right", style="green")
        overall_table.add_column("Embedded", justify="right", style="blue")
        overall_table.add_column("Official URL", style="dim")

        total_embedded = 0
        total_unchanged = 0

        with tqdm(md_files, desc="Ingesting Documents", unit="doc", dynamic_ncols=True) as pbar:
            for f in pbar:
                # Generate clean doc_id relative to root/docs or parent
                try:
                    rel = f.relative_to(path.parent if path.parent.name else path)
                    clean_id = str(rel).replace("\\", "/").removesuffix(".md")
                except Exception:
                    clean_id = f.stem

                pbar.set_postfix_str(f"Doc: {clean_id[:25]}")
                doc = parser.parse_file(f, doc_id=clean_id)
                diff = store.ingest_document(doc)

                embedded_count = len(diff.nodes_needing_embedding)
                unchanged_count = len(diff.unchanged)
                total_embedded += embedded_count
                total_unchanged += unchanged_count

                pbar.set_postfix_str(f"{clean_id[:20]} (+{embedded_count} emb, {unchanged_count} kept)")

                overall_table.add_row(
                    clean_id,
                    doc.title or clean_id,
                    str(unchanged_count),
                    str(embedded_count),
                    doc.url or "-",
                )

        console.print(overall_table)
        console.print(
            f"[bold green]Batch Ingestion Complete![/bold green] Total documents: [bold]{len(md_files)}[/bold] | "
            f"Preserved unchanged: [bold green]{total_unchanged}[/bold green] | "
            f"Newly embedded: [bold blue]{total_embedded}[/bold blue]\n"
        )
        return

    # Single-file ingestion mode
    with tqdm(total=1, desc=f"Parsing {doc_id or path.stem}", unit="doc", dynamic_ncols=True) as pbar:
        doc = parser.parse_file(path, doc_id=doc_id)
        pbar.update(1)

    console.print(Panel(f"[bold green]Parsed Markdown Document: '{doc.doc_id}'[/bold green]"))

    # Display TOC Tree
    tree = Tree(f"[bold yellow]{doc.title}[/bold yellow] ({doc.doc_id})")
    for root in doc.root_nodes:
        print_toc_tree(root, tree)
    console.print(tree)

    # Compute incremental diff and store
    with tqdm(total=len(doc.all_nodes()), desc=f"Diffing & Indexing '{doc.doc_id}'", unit="node", dynamic_ncols=True) as pbar:
        diff = store.ingest_document(doc)
        pbar.update(len(doc.all_nodes()))

    # Print Diff & Selective Embedding Stats
    table = Table(title="Incremental Tree Diff & Embedding Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Details", style="dim")

    table.add_row(
        "[green]Unchanged (Preserved)[/green]",
        str(len(diff.unchanged)),
        "Skipped re-embedding (hashes matched)",
    )
    table.add_row(
        "[yellow]Modified (Re-embedded)[/yellow]",
        str(len(diff.modified)),
        ", ".join([new.path_str for _, new in diff.modified]) or "None",
    )
    table.add_row(
        "[blue]Added (Embedded)[/blue]",
        str(len(diff.added)),
        ", ".join([n.path_str for n in diff.added]) or "None",
    )
    table.add_row(
        "[red]Deleted (Removed)[/red]",
        str(len(diff.deleted)),
        ", ".join([n.path_str for n in diff.deleted]) or "None",
    )
    table.add_row(
        "[magenta]Renamed/Moved[/magenta]",
        str(len(diff.renamed_or_moved)),
        "Metadata updated without re-embedding",
    )

    console.print(table)
    console.print(
        f"[bold green]Ingestion complete![/bold green] Total nodes requiring embedding: [bold]{len(diff.nodes_needing_embedding)}[/bold]\n"
    )


def handle_toc(doc_id: str) -> None:
    store = HybridSearchStore()
    doc = store.get_document(doc_id)
    if not doc:
        console.print(f"[bold red]Document not found:[/bold red] '{doc_id}'")
        available = store.list_documents()
        console.print(f"Available documents: {available}")
        return

    tree = Tree(f"[bold yellow]{doc.title}[/bold yellow] ({doc.doc_id})")
    for root in doc.root_nodes:
        print_toc_tree(root, tree)
    console.print(tree)


def handle_search(query: str, alpha: float = 0.5, top_k: int = 4) -> None:
    store = HybridSearchStore()
    results = store.search(query=query, alpha=alpha, top_k=top_k)

    console.print(
        Panel(f"Search Query: '[bold]{query}[/bold]' | Alpha: [bold]{alpha}[/bold] (Dense: {alpha:.2f}, BM25: {1-alpha:.2f})")
    )

    if not results:
        console.print("[yellow]No matching sections found.[/yellow]")
        return

    for idx, r in enumerate(results, start=1):
        dense_str = f"{r.dense_score:.3f}" if r.dense_score is not None else "N/A"
        bm25_str = f"{r.bm25_score:.3f}" if r.bm25_score is not None else "N/A"

        header = f"[bold cyan]Result #{idx}[/bold cyan] | Score: [bold green]{r.score:.3f}[/bold green] (Dense: {dense_str}, BM25: {bm25_str})"
        content_panel = (
            f"[bold]Citation:[/bold] {r.format_citation()}\n"
            f"[bold]Path:[/bold] {r.path_str}\n\n"
            f"{r.content}"
        )
        console.print(Panel(content_panel, title=header))


def extract_text_from_message(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
        return "".join(parts)
    return str(content)


def handle_chat() -> None:
    store = HybridSearchStore()
    set_store(store)
    app = create_agent_graph()

    doc_count = len(store.list_documents())
    welcome_text = (
        f"[bold cyan]☁️ Arvan Cloud Server AI Assistant (دستیار هوشمند سرور ابری ابر آروان)[/bold cyan]\n\n"
        f"• [bold green]{doc_count} مستند فنی[/bold green] سرور ابری آروان در پایگاه دانش ایندکس شده است.\n"
        f"• سوالات خود را درباره ساخت ابرک، شبکه، دیسک، فایروال، پشتیبان‌گیری، اتصال SSH و تنظیمات بپرسید.\n"
        f"• برای پایان گفتگو کلمه [bold red]exit[/bold red] یا [bold red]quit[/bold red] را وارد کنید."
    )
    console.print(
        Panel(
            welcome_text,
            title="[bold yellow]ابر آروان | Arvan Cloud[/bold yellow]",
            subtitle="Agentic RAG Assistant",
            border_style="cyan",
        )
    )

    messages = []
    while True:
        try:
            query = console.input("[bold blue]You:[/bold blue] ")
            if not query.strip():
                continue
            if query.strip().lower() in ("exit", "quit", "q"):
                console.print("[dim]Ending session. Goodbye![/dim]")
                break

            messages.append(HumanMessage(content=query))
            console.print("[dim]Agent thinking...[/dim]")

            final_message = None
            for event in app.stream({"messages": messages}, stream_mode="values"):
                last_msg = event["messages"][-1]
                if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
                    for call in last_msg.tool_calls:
                        console.print(
                            f"[dim magenta]-> Calling tool:[/dim magenta] [bold]{call['name']}[/bold] with args: {call['args']}"
                        )
                elif isinstance(last_msg, ToolMessage):
                    console.print(f"[dim green]<- Tool executed: {last_msg.name}[/dim green]")
                elif isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    final_message = last_msg

            if final_message:
                messages.append(final_message)
                text_content = extract_text_from_message(final_message)
                console.print(Panel(Markdown(text_content), title="[bold green]Assistant (ابر آروان)[/bold green]", border_style="green"))

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic RAG with Markdown TOC Tree, Diffing, and Hybrid Search"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_p = subparsers.add_parser("ingest", help="Ingest a Markdown file into TOC tree and DB")
    ingest_p.add_argument("file", help="Path to markdown file")
    ingest_p.add_argument("--doc-id", default=None, help="Custom document ID")

    # TOC command
    toc_p = subparsers.add_parser("toc", help="Display TOC tree for an indexed document")
    toc_p.add_argument("doc_id", help="Document ID")

    # Search command
    search_p = subparsers.add_parser("search", help="Perform hybrid search (Dense + BM25)")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--alpha", type=float, default=0.5, help="Hybrid alpha (0=BM25, 1=Dense)")
    search_p.add_argument("--top-k", type=int, default=4, help="Max results to return")

    # Chat command
    subparsers.add_parser("chat", help="Start interactive LangGraph agent chat")

    args = parser.parse_args()

    if args.command == "ingest":
        handle_ingest(args.file, args.doc_id)
    elif args.command == "toc":
        handle_toc(args.doc_id)
    elif args.command == "search":
        handle_search(args.query, args.alpha, args.top_k)
    elif args.command == "chat":
        handle_chat()


if __name__ == "__main__":
    main()

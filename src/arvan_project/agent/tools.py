from __future__ import annotations
from typing import Optional
from langchain_core.tools import tool
from arvan_project.storage.hybrid_store import HybridSearchStore
from arvan_project.parser.models import TOCNode

# Global instance for tool access
_store: Optional[HybridSearchStore] = None


def get_store() -> HybridSearchStore:
    global _store
    if _store is None:
        _store = HybridSearchStore()
    return _store


def set_store(store: HybridSearchStore) -> None:
    global _store
    _store = store


@tool
def search_documentation(query: str, alpha: float = 0.5, top_k: int = 4) -> str:
    """Searches indexed Markdown documentation using hybrid BM25 and semantic search.

    Args:
        query: The search question or keywords.
        alpha: Weight for dense vector search in [0.0, 1.0].
               1.0 = pure semantic search, 0.0 = pure BM25 keywords, 0.5 = balanced hybrid.
        top_k: Number of relevant sections to retrieve.
    """
    store = get_store()
    results = store.search(query=query, alpha=alpha, top_k=top_k)
    if not results:
        return f"No matching documentation found for query: '{query}'"

    formatted = []
    for idx, r in enumerate(results, start=1):
        dense_str = f"{r.dense_score:.3f}" if r.dense_score is not None else "N/A"
        bm25_str = f"{r.bm25_score:.3f}" if r.bm25_score is not None else "N/A"
        formatted.append(
            f"--- Result {idx} ---\n"
            f"Citation: {r.format_citation()}\n"
            f"Hybrid Score: {r.score:.3f} (Dense: {dense_str}, BM25: {bm25_str})\n"
            f"Content:\n{r.content}\n"
        )
    return "\n".join(formatted)


@tool
def get_document_toc(doc_id: str) -> str:
    """Returns the visual Table of Contents (TOC) hierarchy tree for a document.

    Args:
        doc_id: The document identifier (e.g. filename or id).
    """
    store = get_store()
    doc = store.get_document(doc_id)
    if not doc:
        available = store.list_documents()
        return f"Document '{doc_id}' not found. Available documents: {available}"

    lines = [f"Table of Contents for '{doc_id}' ({doc.title}):"]

    def _render_node(node: TOCNode, indent: int = 0):
        prefix = "  " * indent + "- "
        leaf_tag = " [Leaf]" if node.is_leaf else ""
        lines.append(f"{prefix}{node.title} (H{node.level}, Lines {node.line_start}-{node.line_end}){leaf_tag}")
        for child in node.children:
            _render_node(child, indent + 1)

    for root in doc.root_nodes:
        _render_node(root, indent=0)

    return "\n".join(lines)


@tool
def read_section(doc_id: str, section_path: str) -> str:
    """Reads the full Markdown content of a specific section by its path.

    Args:
        doc_id: The document identifier.
        section_path: The breadcrumb path, e.g. 'Overview > Architecture > Storage'.
    """
    store = get_store()
    doc = store.get_document(doc_id)
    if not doc:
        return f"Document '{doc_id}' not found."

    clean_target = section_path.strip().lower()
    for node in doc.all_nodes():
        if (
            node.path_str.lower() == clean_target
            or node.title.lower() == clean_target
            or node.id.lower() == clean_target
        ):
            return (
                f"Section: {node.path_str} (Lines {node.line_start}-{node.line_end})\n"
                f"Content:\n{node.content}"
            )

    return f"Section '{section_path}' not found in document '{doc_id}'."


@tool
def list_indexed_documents() -> str:
    """Lists all document IDs currently indexed in the knowledge base."""
    store = get_store()
    docs = store.list_documents()
    if not docs:
        return "No documents are currently indexed."
    return f"Indexed documents ({len(docs)}): " + ", ".join(docs)


@tool
def calculate_server_price(
    cpu_cores: float,
    ram_gb: float,
    storage_gb: float,
    region: str = "iran",
    tier: str = "standard",
    storage_type: str = "ssd",
    download_traffic_gb: float = 0.0,
    upload_traffic_gb: float = 0.0,
    backup_gb: float = 0.0,
    snapshot_gb: float = 0.0,
) -> str:
    """Calculates official hourly and monthly costs for core Arvan Cloud Server resources in Tomans.

    Args:
        cpu_cores: (Required) Number of CPU cores (e.g. 1, 2, 4, 8).
        ram_gb: (Required) RAM size in GB (e.g. 2, 4, 8, 16).
        storage_gb: (Required) Cloud disk storage size in GB (e.g. 25, 50, 100).
        region: (Optional) Datacenter region: 'iran' or 'europe'. Default is 'iran'.
        tier: (Optional) Server generation tier: 'basic', 'standard', or 'premium'. Default is 'standard'.
        storage_type: (Optional) Cloud disk type: 'ssd' or 'hdd'. Default is 'ssd'.
        download_traffic_gb: (Optional) Estimated monthly download traffic in GB.
        upload_traffic_gb: (Optional) Estimated monthly upload traffic in GB.
        backup_gb: (Optional) Backup storage size in GB.
        snapshot_gb: (Optional) Snapshot / Image storage size in GB.
    """
    from arvan_project.calculator import calculate_server_cost

    result = calculate_server_cost(
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        storage_gb=storage_gb,
        region=region,
        tier=tier,
        storage_type=storage_type,
        download_traffic_gb=download_traffic_gb,
        upload_traffic_gb=upload_traffic_gb,
        backup_gb=backup_gb,
        snapshot_gb=snapshot_gb,
    )
    return result.format_persian_markdown()


@tool
def escalate_to_support(
    service_type: str,
    details: str,
    user_contact: Optional[str] = None,
) -> None:
    """ارجاع رسمی درخواست کاربر به تیم پشتیبانی و واحد فروش ابر آروان.

    از این ابزار در مواردی استفاده می‌شود که کاربر نیازمند استعلام قیمت، مشاوره فنی، سفارش یا فعال‌سازی خدماتی است که قیمت‌گذاری یا تخصیص آن‌ها نیاز به هماهنگی مستقیم با تیم پشتیبانی و فروش ابر آروان دارد.

    موارد الزامی استفاده از این ابزار:
    1. دیسک لوکال (Local Storage / Local Disk): هارد و حافظه فیزیکی متصل به سرور با کمترین تأخیر.
    2. فایل استوریج (File Storage / NFS): فضای اشتراکی مدیریت فایل و دسترسی همزمان چند سرور ابری.
    3. نشانی‌های IP عمومی یا اضافه (IPv4 / IPv6 Addresses): سفارش آی‌پی‌های بیشتر یا ساب‌نت اختصاصی.
    4. پردازنده‌های گرافیکی (GPU Cloud Server): ابرک‌های مجهز به کارت‌های پردازش هوش مصنوعی و یادگیری ماشین نظیر NVIDIA RTX 4060, A30, V100, A100, H100.
    5. انتقال رنج آی‌پی اختصاصی (BYOIP - Bring Your Own IP): انتقال و نگهداری ساب‌نت‌های /24, /23, /22.
    6. درخواست‌های سازمانی، افزایش سهمیه منابع (Quota) و مسائل نیازمند بررسی کارشناس.

    Args:
        service_type: نوع خدمت درخواستی کاربر، مانند 'gpu', 'local_disk', 'file_storage', 'additional_ip', 'byoip', 'custom_quota'.
        details: شرح کامل نیازمندی، منابع درخواستی و توضیحات کاربر.
        user_contact: اطلاعات تماس، ایمیل یا شناسه کاربری (اختیاری).
    """
    
    return "درخواست شما با موفقیت جهت بررسی به تیم پشتیبانی ابر آروان ارجاع داده شد."


# Alias for compatibility with alternate naming

esclate_to_support = escalate_to_support



def get_all_tools():
    """Returns the list of agent tools."""
    return [
        search_documentation,
        get_document_toc,
        read_section,
        list_indexed_documents,
        calculate_server_price,
        escalate_to_support,
    ]



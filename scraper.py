#!/usr/bin/env python3
"""
ArvanCloud Documentation Scraper
Scrapes docs from https://docs.arvancloud.ir/fa/cloud-server/ using MarkItDown
and organizes them into a hierarchical directory structure.
"""

import os
import sys
import io
import argparse
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from markitdown import MarkItDown

# Ensure UTF-8 output in Windows terminals
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = "https://docs.arvancloud.ir/fa/cloud-server"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
}


def load_urls(input_file: str, ensure_complete_tree: bool = True) -> list[str]:
    """Load, strip, deduplicate URLs, and optionally fill missing parent category URLs."""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        raw_urls = [line.strip() for line in f if line.strip()]

    # Normalize trailing slash and deduplicate preserving order
    unique_urls = []
    seen = set()
    for u in raw_urls:
        clean_u = u.rstrip("/") + "/"
        if clean_u not in seen:
            seen.add(clean_u)
            unique_urls.append(clean_u)

    if ensure_complete_tree:
        # Guarantee parent and category index URLs are present for complete hierarchy
        category_candidates = [
            "https://docs.arvancloud.ir/fa/cloud-server/",
            "https://docs.arvancloud.ir/fa/cloud-server/instance/",
            "https://docs.arvancloud.ir/fa/cloud-server/instance/pre-paid/",
            "https://docs.arvancloud.ir/fa/cloud-server/network/",
            "https://docs.arvancloud.ir/fa/cloud-server/volume/",
        ]
        for cat in category_candidates:
            if cat not in seen:
                seen.add(cat)
                unique_urls.append(cat)

    return unique_urls


def determine_file_path(url: str, all_urls: list[str], output_dir: str) -> tuple[str, str]:
    """
    Determine the relative hierarchical filepath for a given documentation URL.
    Returns: (absolute_file_path, relative_file_path)
    """
    clean_url = url.rstrip("/")
    base_clean = BASE_URL.rstrip("/")

    # Relative path from base, e.g. "instance/backup" or ""
    if clean_url == base_clean:
        rel_slug = ""
    elif clean_url.startswith(base_clean + "/"):
        rel_slug = clean_url[len(base_clean) + 1 :]
    else:
        # Fallback for URLs outside base
        parsed = urlparse(clean_url)
        rel_slug = parsed.path.strip("/").replace("fa/", "")

    # Check if this slug is a prefix (parent) for any other URL
    is_parent = False
    for other in all_urls:
        other_clean = other.rstrip("/")
        if other_clean.startswith(base_clean + "/"):
            other_slug = other_clean[len(base_clean) + 1 :]
            if rel_slug and other_slug != rel_slug and other_slug.startswith(rel_slug + "/"):
                is_parent = True
                break

    if not rel_slug:
        # Root page
        rel_file = os.path.join("cloud-server", "README.md")
    elif is_parent:
        # Parent section directory -> README.md inside that directory
        rel_file = os.path.join("cloud-server", rel_slug, "README.md")
    else:
        # Leaf doc inside its respective category directory
        rel_file = os.path.join("cloud-server", f"{rel_slug}.md")

    abs_file = os.path.abspath(os.path.join(output_dir, rel_file))
    return abs_file, rel_file


def clean_article_html(html_content: str) -> tuple[str, str, str]:
    """
    Extract the main <article> tag from Docusaurus page and clean navigational debris.
    Returns: (cleaned_html, title, description)
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract page title and meta description
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"
        title = title.split("|")[0].strip()

    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc = meta_desc.get("content", "").strip() if meta_desc else ""

    article = soup.find("article")
    if not article:
        article = soup.find("main") or soup.find("body") or soup

    # Remove Docusaurus UI elements (breadcrumbs, buttons, sidebars, footer, scripts)
    for el in article.find_all(
        [
            "nav",
            "button",
            "aside",
            "footer",
            "script",
            "style",
            "noscript",
        ]
    ):
        el.decompose()

    # Remove hash links anchors
    for a in article.find_all("a", class_=lambda c: c and "hash-link" in c):
        a.decompose()

    # Remove mobile TOC if still present
    for toc in article.find_all("div", class_=lambda c: c and "tocMobile" in c):
        toc.decompose()

    # Fix relative image URLs to absolute
    for img in article.find_all("img"):
        src = img.get("src")
        if src and not src.startswith(("http://", "https://", "data:")):
            img["src"] = urljoin(BASE_URL + "/", src)

    return str(article), title, desc


def convert_to_markdown(md_engine: MarkItDown, cleaned_html: str, url: str, title: str, desc: str) -> str:
    """Convert cleaned HTML to Markdown using MarkItDown with YAML frontmatter."""
    stream = io.BytesIO(cleaned_html.encode("utf-8"))
    res = md_engine.convert_stream(stream, file_extension=".html")
    raw_md = res.text_content.strip()

    # Ensure H1 title at top if missing
    lines = raw_md.splitlines()
    has_h1 = any(line.startswith("# ") for line in lines[:5])

    frontmatter = [
        "---",
        f'title: "{title}"',
        f'url: "{url}"',
    ]
    if desc:
        clean_desc = desc.replace('"', '\\"')
        frontmatter.append(f'description: "{clean_desc}"')
    frontmatter.append("---\n")

    header_block = "\n".join(frontmatter)
    if not has_h1 and title:
        header_block += f"\n# {title}\n"

    return header_block + "\n\n" + raw_md + "\n"


def build_summary(entries: list[dict], output_dir: str):
    """Generate a clean, structured SUMMARY.md matching the documentation hierarchy."""
    summary_path = os.path.join(output_dir, "cloud-server", "SUMMARY.md")

    # Map relative path to entry
    by_rel = {}
    for entry in entries:
        norm_rel = entry["rel_file"].replace("cloud-server" + os.sep, "").replace("\\", "/")
        by_rel[norm_rel] = entry

    # Preferred hierarchical presentation matching ArvanCloud sidebar
    structure = [
        ("سرور ابری (آغاز کار)", "README.md", [
            ("ابرک", "instance/README.md", [
                ("بسته‌های پیش‌پرداخت", "instance/pre-paid.md", []),
                ("دیتاسنترها و بسته‌ها", "instance/datacenter-plans.md", []),
                ("اتصال به ابرک", "instance/connection.md", []),
                ("بازیابی اطلاعات ابرک", "instance/rescue.md", []),
                ("راه‌اندازی اپلیکیشن بازارچه", "instance/marketplace.md", []),
                ("بکاپ", "instance/backup.md", []),
            ]),
            ("شبکه", "network/README.md", [
                ("شبکه خصوصی", "network/private.md", []),
                ("شبکه سیستم‌عامل", "network/os.md", []),
                ("آدرس IPv6", "network/ipv6.md", []),
                ("تنظیمات Routing", "network/routing.md", []),
                ("رکورد PTR ابرک", "network/ptr.md", []),
                ("انتقال رنج IP", "network/byoip.md", []),
            ]),
            ("فایروال", "firewall.md", []),
            ("مدیریت دیسک و تصاویر", None, [
                ("دیسک", "volume/README.md", []),
                ("فایل ‌استوریج", "volume/file-storage.md", []),
                ("پارتیشن‌بندی و Mount", "volume/partition.md", []),
                ("سیستم‌عامل شخصی", "images/custom-os.md", []),
                ("اسنپ‌شات", "images/snapshot.md", []),
            ]),
            ("سرور اختصاصی ابری", "dedicated-server.md", []),
            ("مدیریت دسترسی‌ها", "iam.md", []),
            ("محدودیت منابع سرور ابری", "quota.md", []),
        ]),
    ]

    lines = ["# ساختار درختی و فهرست مستندات سرور ابری آروان‌کلاد (Table of Contents)\n\n"]

    used_rels = set()

    def render_tree(items, level=0):
        indent = "  " * level
        for label, rel, children in items:
            if rel:
                used_rels.add(rel)
                page_title = by_rel[rel]["title"] if rel in by_rel else label
                lines.append(f"{indent}* [{page_title}]({rel})\n")
            else:
                lines.append(f"{indent}* **{label}**\n")
            if children:
                render_tree(children, level + 1)

    render_tree(structure)

    # Any remaining files not in the explicit structure
    remaining = [r for r in by_rel if r not in used_rels]
    if remaining:
        lines.append("\n## سایر مستندات\n\n")
        for r in sorted(remaining):
            title = by_rel[r]["title"] or r
            lines.append(f"* [{title}]({r})\n")

    summary_content = "".join(lines)
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_content)

    print(f"Generated Hierarchical Table of Contents at: {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Scrape ArvanCloud docs with MarkItDown")
    parser.add_argument(
        "--input", "-i", default="x3.txt", help="Path to text file containing URLs"
    )
    parser.add_argument(
        "--output", "-o", default="docs", help="Output directory for saved documentation"
    )
    parser.add_argument(
        "--ensure-parents",
        action="store_true",
        default=True,
        help="Ensure parent section pages (e.g. network/) are included for full hierarchy",
    )
    args = parser.parse_args()

    print(f"Loading URLs from {args.input}...")
    urls = load_urls(args.input, ensure_complete_tree=args.ensure_parents)
    print(f"Found {len(urls)} target URLs to process.")

    md_engine = MarkItDown()
    session = requests.Session()
    session.headers.update(HEADERS)

    entries = []
    success_count = 0
    fail_count = 0

    for idx, url in enumerate(urls, 1):
        abs_path, rel_path = determine_file_path(url, urls, args.output)
        print(f"[{idx}/{len(urls)}] Fetching: {url}")
        print(f"    -> Destination: {rel_path}")

        try:
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                print(f"    [!] Error HTTP {resp.status_code} for {url}")
                fail_count += 1
                continue

            cleaned_html, title, desc = clean_article_html(resp.text)
            markdown_content = convert_to_markdown(
                md_engine, cleaned_html, url, title, desc
            )

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            entries.append({
                "url": url,
                "title": title,
                "rel_file": rel_path,
                "abs_file": abs_path,
            })
            success_count += 1

        except Exception as e:
            print(f"    [!] Failed to process {url}: {e}")
            fail_count += 1

    # Generate SUMMARY.md
    build_summary(entries, args.output)

    print("\n" + "=" * 50)
    print(f"Documentation scraping completed!")
    print(f"Total Successful: {success_count}")
    print(f"Total Failed:     {fail_count}")
    print(f"Saved into:       {os.path.abspath(args.output)}")
    print("=" * 50)


if __name__ == "__main__":
    main()

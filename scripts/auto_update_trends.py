#!/usr/bin/env python3
"""
auto_update_trends.py
=====================
Fetches the latest AI-agent research papers from the arXiv API and appends
a "Recent Research" section to ``docs/index.md``.

This script is designed to be run in CI (see ``.github/workflows/auto-update-docs.yml``)
but can also be executed locally:

    python scripts/auto_update_trends.py

Requirements
------------
    pip install requests

Exit codes
----------
  0 — Ran successfully (even if no new papers were found).
  1 — Fatal error (network failure, file I/O error, etc.).
"""

import datetime
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' is not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ARXIV_API_URL = "https://export.arxiv.org/api/query"
SEARCH_QUERY = "ti:autonomous+agent+AND+ti:LLM"
MAX_RESULTS = 5
DOCS_INDEX = Path("docs/index.md")
ARXIV_NS = "http://www.w3.org/2005/Atom"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_papers(query: str, max_results: int) -> list[dict]:
    """Query arXiv and return a list of paper dicts."""
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    try:
        response = requests.get(ARXIV_API_URL, params=params, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[ERROR] arXiv API request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    root = ET.fromstring(response.text)
    papers: list[dict] = []

    for entry in root.findall(f"{{{ARXIV_NS}}}entry"):
        title_el = entry.find(f"{{{ARXIV_NS}}}title")
        summary_el = entry.find(f"{{{ARXIV_NS}}}summary")
        link_el = entry.find(f"{{{ARXIV_NS}}}id")
        published_el = entry.find(f"{{{ARXIV_NS}}}published")

        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else "Untitled"
        summary = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""
        published = (published_el.text or "")[:10] if published_el is not None else ""

        # Truncate long summaries for readability
        if len(summary) > 200:
            summary = summary[:197] + "..."

        papers.append({"title": title, "summary": summary, "url": url, "published": published})

    return papers


def build_section(papers: list[dict]) -> str:
    """Build a Markdown section string from the list of papers."""
    today = datetime.date.today().isoformat()
    lines = [
        "",
        f"## 🔬 Recent Research Trends *(auto-updated {today})*",
        "",
        "The following papers were automatically sourced from [arXiv](https://arxiv.org) "
        "and are relevant to autonomous agent architecture:",
        "",
    ]
    for p in papers:
        lines.append(f"- **[{p['title']}]({p['url']})** ({p['published']})")
        if p["summary"]:
            lines.append(f"  > {p['summary']}")
        lines.append("")

    lines.append("---")
    return "\n".join(lines)


def update_index(papers: list[dict]) -> None:
    """Replace or append the 'Recent Research Trends' section in docs/index.md."""
    if not DOCS_INDEX.exists():
        print(f"[WARN] {DOCS_INDEX} not found — creating it.", file=sys.stderr)
        DOCS_INDEX.parent.mkdir(parents=True, exist_ok=True)
        DOCS_INDEX.write_text("# The Agent Bible Documentation\n", encoding="utf-8")

    current = DOCS_INDEX.read_text(encoding="utf-8")

    # Remove any existing auto-generated section before re-inserting
    marker = "## 🔬 Recent Research Trends"
    if marker in current:
        current = current[: current.index(marker)].rstrip()

    new_section = build_section(papers)
    DOCS_INDEX.write_text(current + "\n" + new_section + "\n", encoding="utf-8")
    print(f"✅ Updated {DOCS_INDEX} with {len(papers)} paper(s).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"🔍 Fetching top {MAX_RESULTS} papers from arXiv (query: '{SEARCH_QUERY}')…")
    papers = fetch_papers(SEARCH_QUERY, MAX_RESULTS)

    if not papers:
        print("[WARN] No papers returned — docs/index.md left unchanged.")
        sys.exit(0)

    update_index(papers)


if __name__ == "__main__":
    main()

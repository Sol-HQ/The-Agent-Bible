#!/usr/bin/env python3
"""
validate_links.py
=================
Scans Markdown files for internal relative links and verifies that every
referenced file or directory actually exists on disk.

Usage
-----
    python scripts/validate_links.py [directory ...]

If no directories are provided the script scans the ``docs/`` folder.

Exit codes
----------
  0 — All checked links resolve to existing targets.
  1 — One or more broken links were found.
"""

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Regex to extract Markdown link targets: [text](target)
_LINK_RE = re.compile(r'\[(?:[^\[\]]*)\]\(([^)]+)\)')


def _is_external(href: str) -> bool:
    """Return True if href is an absolute URL (http/https/mailto/…)."""
    parsed = urlparse(href)
    return bool(parsed.scheme)


def check_file(md_path: Path) -> list[dict]:
    """Return a list of broken-link records found in *md_path*."""
    broken: list[dict] = []
    source = md_path.read_text(encoding="utf-8")

    for match in _LINK_RE.finditer(source):
        href = match.group(1).strip()

        # Strip fragment identifiers (#section)
        href_no_frag = href.split("#")[0]

        if not href_no_frag:
            # Pure fragment link — nothing to check on disk
            continue

        if _is_external(href_no_frag):
            continue

        target = (md_path.parent / href_no_frag).resolve()

        if not target.exists():
            line_num = source[: match.start()].count("\n") + 1
            broken.append(
                {
                    "source": str(md_path),
                    "line": line_num,
                    "href": href,
                    "resolved": str(target),
                }
            )

    return broken


def scan_directory(directory: Path) -> list[dict]:
    """Recursively find all .md files under *directory* and check their links."""
    all_broken: list[dict] = []
    for md_file in sorted(directory.rglob("*.md")):
        all_broken.extend(check_file(md_file))
    return all_broken


def main() -> None:
    args = sys.argv[1:]
    targets = [Path(a) for a in args] if args else [Path("docs")]

    all_broken: list[dict] = []
    md_count = 0

    for target in targets:
        if target.is_file() and target.suffix.lower() == ".md":
            all_broken.extend(check_file(target))
            md_count += 1
        elif target.is_dir():
            before = len(all_broken)
            results = scan_directory(target)
            all_broken.extend(results)
            md_count += sum(1 for _ in target.rglob("*.md"))
        else:
            print(f"[WARN] Skipping '{target}' — not a Markdown file or directory.")

    if all_broken:
        print(f"\n❌ Link validation FAILED — {len(all_broken)} broken link(s) found:\n")
        for rec in all_broken:
            print(
                f"  Source : {rec['source']}:{rec['line']}\n"
                f"  Link   : {rec['href']}\n"
                f"  Target : {rec['resolved']} (NOT FOUND)\n"
            )
        sys.exit(1)

    print(f"✅ All internal links valid — scanned {md_count} Markdown file(s).")
    sys.exit(0)


if __name__ == "__main__":
    main()

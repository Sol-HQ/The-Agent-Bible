#!/usr/bin/env python3
"""
Cache snapshot script
- Takes a list of URLs (CLI args or newline-separated file)
- Scrapes page text and saves as timestamped files into brain-material/

Usage:
  python3 scripts/cache_snapshot.py https://example.com/page1 https://example.com/page2
  python3 scripts/cache_snapshot.py --file urls.txt
"""
import os
import sys
import time
import argparse
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.dirname(__file__))
BRAIN_DIR = os.path.join(BASE, "implementations", "local-sovereign-agent", "brain-material")
os.makedirs(BRAIN_DIR, exist_ok=True)

def sanitize_filename(s: str) -> str:
    return ''.join(c for c in s if c.isalnum() or c in ['.', '-', '_']).rstrip()

def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # prefer article/main tags
    article = soup.find(['article', 'main'])
    if article:
        text = '\n'.join(p.get_text(separator=' ', strip=True) for p in article.find_all('p'))
        if len(text) > 50:
            return text
    # fallback: gather <p>
    paragraphs = soup.find_all('p')
    text = '\n'.join(p.get_text(separator=' ', strip=True) for p in paragraphs)
    if text.strip():
        return text
    # last resort: body text
    body = soup.get_text(separator=' ', strip=True)
    return body

def cache_url(url: str) -> str:
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return ""
    text = extract_text_from_html(resp.text)
    if not text.strip():
        print(f"No textual content found at {url}")
        return ""
    parsed = urlparse(url)
    ts = time.strftime('%Y%m%dT%H%M%S')
    host = sanitize_filename(parsed.netloc.replace(':', '_'))
    path = sanitize_filename(parsed.path.replace('/', '_'))[:80] or 'root'
    fname = f"{ts}_{host}_{path}.txt"
    out_path = os.path.join(BRAIN_DIR, fname)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(f"# Source: {url}\n# Cached: {ts}\n\n")
        fh.write(text)
    print(f"Saved snapshot: {out_path}")
    return out_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', help='File containing newline-separated URLs')
    parser.add_argument('urls', nargs='*')
    args = parser.parse_args()
    urls = []
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    urls.append(line)
    urls.extend(args.urls)
    if not urls:
        print('No URLs provided')
        sys.exit(1)
    for u in urls:
        cache_url(u)

if __name__ == '__main__':
    main()

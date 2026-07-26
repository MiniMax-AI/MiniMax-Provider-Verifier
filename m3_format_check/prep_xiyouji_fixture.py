#!/usr/bin/env python3
"""
Build fixture text file: ~512k chars of Journey-to-the-West (西遊記) source text
from zh.wikisource.org.

Output: fixtures/xiyouji_long_context.txt
- Downloads chapters 1..N sequentially from wikisource (action=raw)
- Strips MediaWiki headers/markup minimally so the model sees mostly clean prose
- Concatenates until char count >= TARGET_CHARS, then trims to exactly TARGET_CHARS

Run once locally; the fixture is reused by m3_text_tests test_17_05.
"""
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

TARGET_CHARS = 660_000  # ~660k chars; calibrated so prompt_tokens clearly > 524288
HERE = Path(__file__).parent
OUT_FILE = HERE / "fixtures" / "xiyouji_long_context.txt"

BASE = "https://zh.wikisource.org/wiki/" + quote("西遊記") + "/"


def fetch_chapter(idx: int) -> str:
    """Fetch one chapter's raw wikitext."""
    title = f"第{idx:03d}回"
    url = BASE + quote(title) + "?action=raw"
    with httpx.Client(timeout=30.0, follow_redirects=True) as c:
        resp = c.get(url, headers={"User-Agent": "xyj-fixture/1.0"})
    resp.raise_for_status()
    return resp.text


def strip_wikitext(text: str) -> str:
    """Best-effort: remove the {{header}} block at top, comments, and
    most templates/links/markers so the model reads mostly plain prose."""
    # Header block at the top
    text = re.sub(r"\{\{header[^}]*\}\}\n?", "", text, flags=re.S | re.I)
    # HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # Other templates {{...}}
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # ref/links [[xxx|yyy]] -> yyy ;  [[xxx]] -> xxx
    text = re.sub(r"\[\[[^\[\]\|]*\|([^\[\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", text)
    # External links
    text = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", text)
    # bold/italic
    text = re.sub(r"'''([^']*)'''", r"\1", text)
    text = re.sub(r"''([^']*)''", r"\1", text)
    # ref tags
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    # Multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if OUT_FILE.exists() and OUT_FILE.stat().st_size >= TARGET_CHARS * 3:
        print(f"[skip] {OUT_FILE} already exists ({OUT_FILE.stat().st_size} bytes)")
        return
    pieces = []
    total = 0
    for idx in range(1, 101):
        try:
            print(f"  fetching chapter {idx:03d}...", end=" ", flush=True)
            raw = fetch_chapter(idx)
            clean = strip_wikitext(raw)
            pieces.append(clean)
            total += len(clean)
            print(f"+{len(clean)} chars (total={total})")
        except httpx.HTTPError as e:
            print(f"FAILED: {e}")
            continue
        if total >= TARGET_CHARS + 50_000:  # safety margin so we can trim cleanly
            break
        time.sleep(0.5)  # be nice to wikisource

    joined = "\n\n".join(pieces)
    # Trim to exactly TARGET_CHARS, but break at a paragraph boundary if possible
    if len(joined) > TARGET_CHARS:
        cut = joined.rfind("\n\n", 0, TARGET_CHARS)
        if cut < TARGET_CHARS - 5000:  # no boundary close enough; hard cut
            cut = TARGET_CHARS
        joined = joined[:cut]

    OUT_FILE.write_text(joined, encoding="utf-8")
    print(f"\n[done] wrote {OUT_FILE} ({len(joined):,} chars)")


if __name__ == "__main__":
    main()

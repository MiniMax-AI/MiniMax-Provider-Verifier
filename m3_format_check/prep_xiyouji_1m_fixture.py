#!/usr/bin/env python3
"""Build the approximately 1M-token Journey-to-the-West fixture."""
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "fixtures" / "xiyouji_long_context.txt"
OUTPUT = HERE / "fixtures" / "xiyouji_1m_long_context.txt"
TARGET_CHARS = 1_320_000

source = "\n".join(
    line.rstrip() for line in SOURCE.read_text(encoding="utf-8").splitlines()
)
parts = []
while sum(len(part) for part in parts) < TARGET_CHARS:
    parts.append(source)
text = "\n\n".join(parts)[:TARGET_CHARS]
OUTPUT.write_text(text, encoding="utf-8")
print(f"wrote {OUTPUT} ({len(text):,} chars)")

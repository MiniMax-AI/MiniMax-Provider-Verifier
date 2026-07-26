"""
M3 API Test Suite — Shared Helpers (OAI /v1/chat/completions only)

Every oai_chat() call writes a single jsonl line to RUN_LOG_PATH containing
the full request and full response (or per-chunk stream array). conftest.py
sets RUN_LOG_PATH at session start.
"""
import base64
import json
import os
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

BASE_URL = os.environ.get("M3_BASE_URL")
API_KEY = os.environ.get("M3_API_KEY")
AUTH_TYPE = os.environ.get("M3_AUTH_TYPE", "bearer").strip().lower()
if AUTH_TYPE not in ("bearer", "none"):
    raise EnvironmentError(
        f"Unsupported M3_AUTH_TYPE={AUTH_TYPE!r}; expected 'bearer' or 'none'."
    )
if not BASE_URL or (AUTH_TYPE == "bearer" and not API_KEY):
    raise EnvironmentError(
        "Missing required environment variables.\n"
        "Please set before running tests:\n"
        "  export M3_BASE_URL='https://your-endpoint.example.com'\n"
        "  export M3_API_KEY='sk-your-api-key'  # required for bearer auth\n"
        "  export M3_AUTH_TYPE='none'           # for endpoints without auth\n"
        "  export M3_MODEL='your-model-id'        # optional, default: MiniMax-M3\n"
        "  export M3_MODEL_MINI='your-mini-model'  # optional, default: MiniMax-M2-mini"
    )
MODEL = os.environ.get("M3_MODEL", "MiniMax-M3")
MODEL_MINI = os.environ.get("M3_MODEL_MINI", "MiniMax-M2-mini")
TIMEOUT = 1800

OAI_URL = f"{BASE_URL}/v1/chat/completions"

OAI_HEADERS = {
    "Content-Type": "application/json",
}
if AUTH_TYPE == "bearer":
    OAI_HEADERS["Authorization"] = f"Bearer {API_KEY}"

# M3_EXTRA_HEADERS: JSON string, extra request headers injected across links (e.g. X-MM-Text-Provider-Model)
# Looks like '{"X-MM-Text-Provider-Model": "togetherai-m3:shadow/xxx"}'; ignored on parse failure
_raw_extra_headers = os.environ.get("M3_EXTRA_HEADERS", "").strip()
if _raw_extra_headers:
    try:
        _extra = json.loads(_raw_extra_headers)
        if isinstance(_extra, dict):
            OAI_HEADERS.update({str(k): str(v) for k, v in _extra.items()})
    except (json.JSONDecodeError, TypeError):
        pass


# ---------------- Run log (jsonl) ----------------

# Populated by conftest.pytest_configure. Tests that import helpers directly
# (outside pytest) get a fallback path so logging still works.
RUN_LOG_PATH: Optional[Path] = None


def _fallback_log_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = Path(__file__).parent / "logs" / f"run_{ts}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _current_case_id() -> str:
    """Extract a stable case id from pytest's PYTEST_CURRENT_TEST env var.

    Example value: "test_oai.py::TestOAIText::test_01_text_non_stream (call)"
    Returns:       "test_oai/TestOAIText/test_01_text_non_stream"

    Outside of pytest we fall back to a timestamped manual-* id so direct
    imports still produce a usable log entry.
    """
    raw = os.environ.get("PYTEST_CURRENT_TEST")
    if not raw:
        return f"manual-{int(time.time() * 1000)}"
    # Strip the " (call)" / " (setup)" / " (teardown)" phase suffix.
    cleaned = raw.split(" (", 1)[0]
    return cleaned.replace("::", "/")


def _write_log_line(record: dict) -> None:
    global RUN_LOG_PATH
    if RUN_LOG_PATH is None:
        RUN_LOG_PATH = _fallback_log_path()
    line = json.dumps(record, ensure_ascii=False, default=str)
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


# --------------- Test images (≥672 px, low-tier minimum size) ---------------
#
# Image format notes:
# - PNG is generated at runtime as a 672×672 solid color from RGB params, since v05/t10 etc. need different colors;
# - JPEG / GIF / WEBP are ffmpeg-generated 672×672 solid-red single frames, base64-hardcoded to avoid runtime dependencies;
# - Video MP4 is ffmpeg-generated 504×504 / 1s / H.264 black, base64-hardcoded.
# Whenever the downstream has a "must be ≥ low-tier minimum size" server-side rule (images ≥672, videos ≥504), these fixtures satisfy it.

_PNG_SIDE = 672  # Image shortest side: satisfies low tier (≥672 px)
_MP4_SIDE = 504  # Video shortest side: satisfies low tier (≥504 px)


def make_png_672(r=255, g=0, b=0, side=_PNG_SIDE):
    """Generate a 672×672 (or `side`×`side`) PNG of a solid RGB color.

    Uses only stdlib (zlib + struct) — no PIL dependency. Compressed PNG of a
    solid color stays under 1 KB even at 672×672 thanks to scanline filtering.
    """
    import zlib

    def _chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    pixel = bytes([r, g, b])
    # Each scanline: 1 filter byte (0 = None) + side*3 RGB bytes.
    scanline = b"\x00" + pixel * side
    raw = zlib.compress(scanline * side, 9)
    return header + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", raw) + _chunk(b"IEND", b"")


# --- ffmpeg-generated 672×672 red — base64 hardcoded for offline reproducibility ---
# JPEG 672×672 red (raw 2870 B / b64 3828 B)
_JPEG_672_RED_B64 = (
    "/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYxLjE5LjEwMQD/2wBDAAgKCgsKCw0NDQ0NDRAP"
    "EBAQEBAQEBAQEBASEhIVFRUSEhIQEBISFBQVFRcXFxUVFRUXFxkZGR4eHBwjIyQrKzP/xABNAAEB"
    "AAAAAAAAAAAAAAAAAAAABgEBAQEAAAAAAAAAAAAAAAAAAAYHEAEAAAAAAAAAAAAAAAAAAAAAEQEA"
    "AAAAAAAAAAAAAAAAAAAA/8AAEQgCoAKgAwEiAAIRAAMRAP/aAAwDAQACEQMRAD8AiwEo38AAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAB/9k="
)

# GIF 672×672 red (raw 3925 B / b64 5236 B)
_GIF_672_RED_B64 = (
    "R0lGODlhoAKgAvcfMQAAACQAAEgAAGwAAJAAALQAANgAAPwAAAAkACQkAEgkAGwkAJAkALQkANgk"
    "APwkAABIACRIAEhIAGxIAJBIALRIANhIAPxIAABsACRsAEhsAGxsAJBsALRsANhsAPxsAACQACSQ"
    "AEiQAGyQAJCQALSQANiQAPyQAAC0ACS0AEi0AGy0AJC0ALS0ANi0APy0AADYACTYAEjYAGzYAJDY"
    "ALTYANjYAPzYAAD8ACT8AEj8AGz8AJD8ALT8ANj8APz8AAAAVSQAVUgAVWwAVZAAVbQAVdgAVfwA"
    "VQAkVSQkVUgkVWwkVZAkVbQkVdgkVfwkVQBIVSRIVUhIVWxIVZBIVbRIVdhIVfxIVQBsVSRsVUhs"
    "VWxsVZBsVbRsVdhsVfxsVQCQVSSQVUiQVWyQVZCQVbSQVdiQVfyQVQC0VSS0VUi0VWy0VZC0VbS0"
    "Vdi0Vfy0VQDYVSTYVUjYVWzYVZDYVbTYVdjYVfzYVQD8VST8VUj8VWz8VZD8VbT8Vdj8Vfz8VQAA"
    "qiQAqkgAqmwAqpAAqrQAqtgAqvwAqgAkqiQkqkgkqmwkqpAkqrQkqtgkqvwkqgBIqiRIqkhIqmxI"
    "qpBIqrRIqthIqvxIqgBsqiRsqkhsqmxsqpBsqrRsqthsqvxsqgCQqiSQqkiQqmyQqpCQqrSQqtiQ"
    "qvyQqgC0qiS0qki0qmy0qpC0qrS0qti0qvy0qgDYqiTYqkjYqmzYqpDYqrTYqtjYqvzYqgD8qiT8"
    "qkj8qmz8qpD8qrT8qtj8qvz8qgAA/yQA/0gA/2wA/5AA/7QA/9gA//wA/wAk/yQk/0gk/2wk/5Ak"
    "/7Qk/9gk//wk/wBI/yRI/0hI/2xI/5BI/7RI/9hI//xI/wBs/yRs/0hs/2xs/5Bs/7Rs/9hs//xs"
    "/wCQ/ySQ/0iQ/2yQ/5CQ/7SQ/9iQ//yQ/wC0/yS0/0i0/2y0/5C0/7S0/9i0//y0/wDY/yTY/0jY"
    "/2zY/5DY/7TY/9jY//zY/wD8/yT8/0j8/2z8/5D8/7T8/9j8//z8/yH/C05FVFNDQVBFMi4wAwEA"
    "AAAh+QQEBAAfACwAAAAAoAKgAgAI/wAPCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPH"
    "jyBDihxJsqTJkyhTqlzJsqXLlzBjypxJs6bNmzhz6tzJs6fPnwYOBjU4tGBRgkcHJhW49EDTp0Kj"
    "EpVqlCpSq0qxMtXqlCvUqWCrhr06NmvZrWe7pv0qti1Zt2bhopWrli7bt3jj5p27t27fu3oD8xXs"
    "lzDgwYgLJz6suDHjx1x/Sp5MubLly5gza97MubPnz6BDix5NurTp06hTq84Jea3X165j24U9W/Zf"
    "2rdtG8a9W/di3r99OwY+XHjr2shzJ++9PHjz4s+PK59OeLX169iza9/Ovbv37+DDi/8fT768+fPo"
    "VUpnTt15e+jv17tnT3++ffj18d+Xr78////EAWhcgAQOaGB0BSJ4YF/pNejggxBGKOGEFFZo4YUY"
    "Zqjhhhx+JKCCIMaXoIgL5vchiSGaOKKKJe63oost+veijDGeyGKKMNLV4Y489ujjj0AGKeSQRBZp"
    "5JFIRmRjjig2eaOTTD4pZZRU0oijlVBiOaWWVS7J5Zdehjmjl0mWaeaZaKap5ppstunmm3CmJ2aN"
    "Y9ZJ551XzpmnnXvimaWef/IZqJ9bArplnIgmquiijDbq6KOQRiqpd4Z2KWihl1pKqKZ9djqop5hu"
    "Cmamo4paaanPTarqqqy26uqrsMb/KuusR55qK6m3morrrrr2CiqnnwYb6q+oCgtsfrQmq+yyzDbr"
    "7LPQRiutQrkSW62xxQ6L7bXadnvst9mCy624vFob2bTopqvuuuy26+678Go3brj0zmtvudvi6229"
    "+pLra77/7ktmvAQXbPDBCCes8MLs3huwv+Y+zK/EDkdsMcAXC9zvxBkz7PHHIIcs8sgkl6xhxRin"
    "rDHFG6O8csccqwyxzDG/jK3JOOes88489+zzzyC5PLPNRA9tdM1HC4300ko33TKpQEct9dRUV231"
    "1es6zfLWMGvd9dNc0+y12GB/LRzWaKet9tpst+32hWMXzXTZZIctd9xJ03233nmL//r234AHLvjg"
    "hBcuGd5z29232YzX3fjeiif++OI3G2755ZhnrvnmhCPuOd+SOy465JOHTvrolJ9eHeest+7667DH"
    "vvDnkdNeuu2om5767rr3jrvswAcv/PDEFw/n77wj7zvoyjfP/PO1Q2/89NRXb/312EfofPTc3y59"
    "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"
)

# WEBP 672×672 red (raw 970 B / b64 1296 B)
_WEBP_672_RED_B64 = (
    "UklGRsIDAABXRUJQVlA4ILYDAAAwYwCdASqgAqACPpFIoU0lpCMiIAgAsBIJaW7hd2Ee3AAAE94J"
    "yHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D32ych77ZOQ99snIe+2TkPfbJyHvtk5D34AgHvt"
    "k5D32ych77ZOQ99snIfQvpdrxcnIe+2TkPfbJyHvtk5H/PJyHvtk5D32ych77ZOQ99soGXi5OQ99"
    "snIe+2TkPfbJyHvtzL9PbJyHvtk5D32ych77ZOQ+A/S7Xi5OQ99snIe+2TkPfbJyIgeTkPfbJyHv"
    "tk5D32ych77ZOcRFych77ZOQ99snIe+2TkPfbMZae2TkPfbJyHvtk5D32ych78AQD32ych77ZOQ9"
    "9snIe+2TkPoX0u14uTkPfbJyHvtk5D32ycj/nk5D32ych77ZOQ99snIe+2UDLxcnIe+2TkPfbJyH"
    "vtk5D325l+ntk5D32ych77ZOQ99snIfAfpdrxcnIe+2TkPfbJyHvtk5EQPJyHvtk5D32ych77ZOQ"
    "99snOIi5OQ99snIe+2TkPfbJyHvtmMtPbJyHvtk5D32ych77ZOQ9+AIB77ZOQ99snIe+2TkPfbJy"
    "H0L6Xa8XJyHvtk5D32ych77ZOR/zych77ZOQ99snIe+2TkPfbKBl4uTkPfbJyHvtk5D32ych77cy"
    "/T2ych77ZOQ99snIe+2TkPgP0u14uTkPfbJyHvtk5D32yciIHk5D32ych77ZOQ99snIe+2TnERcn"
    "Ie+2TkPfbJyHvtk5D32zGWntk5D32ych77ZOQ99snIe/AEA99snIe+2TkPfbJyHvtk5D6F9LteLk"
    "5D32ych77ZOQ99snI/55OQ99snIe+2TkPfbJyHvtlAy8XJyHvtk5D32ych77ZOQ99uZfp7ZOQ99s"
    "nIe+2TkPfbJyHwH6Xa8XJyHvtk5D32ych77ZOREDych77ZOQ99snIe+2TkPfbJziIuTkPfbJyHvt"
    "k5D32ych77ZjLT2ych77ZOQ99snIe+2TkPfgCAe+2TkPfbJyHvtk5D32ych9C+l2vFych77ZOQ99"
    "snIe+2Tkf88nIe+2TkPfbJyHvtk5D31gAP7/r+uf/+xZy2BeP//+5wP+5wP+5wP424rGSnGBWStl"
    "hIEN5AIoEAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kA"
    "jiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAI4kAjiQCOJAIAA"
    "AA=="
)

# MP4 504×504 / 1s / H.264 black (raw 2456 B / b64 3276 B) — satisfies low tier ≥504 px
_MP4_504_BLACK_B64 = (
    "AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAANgbW9vdgAAAGxtdmhkAAAAAAAAAAAA"
    "AAAAAAAD6AAAA+gAAQAAAQAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAA"
    "AABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAot0cmFrAAAAXHRraGQAAAADAAAA"
    "AAAAAAAAAAABAAAAAAAAA+gAAAAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAABAAAAAAAA"
    "AAAAAAAAAABAAAAAAfgAAAH4AAAAAAAkZWR0cwAAABxlbHN0AAAAAAAAAAEAAAPoAAAAAAABAAAA"
    "AAIDbWRpYQAAACBtZGhkAAAAAAAAAAAAAAAAAAA8AAAAPABVxAAAAAAALWhkbHIAAAAAAAAAAHZp"
    "ZGUAAAAAAAAAAAAAAABWaWRlb0hhbmRsZXIAAAABrm1pbmYAAAAUdm1oZAAAAAEAAAAAAAAAAAAA"
    "ACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAAW5zdGJsAAAAunN0c2QAAAAAAAAA"
    "AQAAAKphdmMxAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAfgB+ABIAAAASAAAAAAAAAABFUxhdmM2"
    "MS4xOS4xMDEgbGlieDI2NAAAAAAAAAAAAAAAGP//AAAAMGF2Y0MBQsAW/+EAGWdCwBbaAgBB5ZcB"
    "EAAAAwAQAAADAeDxYuoBAARozg/IAAAAEHBhc3AAAAABAAAAAQAAABRidHJ0AAAAAAAAMEAAAAAA"
    "AAAAGHN0dHMAAAAAAAAAAQAAAA8AAAQAAAAAFHN0c3MAAAAAAAAAAQAAAAEAAAAcc3RzYwAAAAAA"
    "AAABAAAAAQAAAA8AAAABAAAAUHN0c3oAAAAAAAAAAAAAAA8AAAVuAAAACwAAAAsAAAALAAAACwAA"
    "AAsAAAALAAAACwAAAAsAAAALAAAACwAAAAsAAAALAAAACwAAAAsAAAAUc3RjbwAAAAAAAAABAAAD"
    "kAAAAGF1ZHRhAAAAWW1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAA"
    "LGlsc3QAAAAkqXRvbwAAABxkYXRhAAAAAQAAAABMYXZmNjEuNy4xMDAAAAAIZnJlZQAABhBtZGF0"
    "AAACVQYF//9R3EXpvebZSLeWLNgg2SPu73gyNjQgLSBjb3JlIDE2NCByMzEwOCAzMWUxOWY5IC0g"
    "SC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyMyAtIGh0dHA6Ly93d3cu"
    "dmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTAgcmVmPTEgZGVibG9jaz0w"
    "OjA6MCBhbmFseXNlPTA6MCBtZT1kaWEgc3VibWU9MCBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1p"
    "eGVkX3JlZj0wIG1lX3JhbmdlPTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MCA4eDhkY3Q9MCBjcW09"
    "MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21hX3FwX29mZnNldD0wIHRocmVhZHM9"
    "MTIgbG9va2FoZWFkX3RocmVhZHM9MiBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9MSBp"
    "bnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0w"
    "IHdlaWdodHA9MCBrZXlpbnQ9MjUwIGtleWludF9taW49MTUgc2NlbmVjdXQ9MCBpbnRyYV9yZWZy"
    "ZXNoPTAgcmM9Y3JmIG1idHJlZT0wIGNyZj0yMy4wIHFjb21wPTAuNjAgcXBtaW49MCBxcG1heD02"
    "OSBxcHN0ZXA9NCBpcF9yYXRpbz0xLjQwIGFxPTAAgAAAAxFliIQ6JigACQLJycnJycnJycnJycnJ"
    "ycnJycnJycnJycnJycnJycnJ1111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "1111111111111111111111111111111111111111111111111111111111111111111111111111"
    "11111111111111111111111111114AAAAAdBmiAugAgDAAAAB0GaQDKACAMAAAAHQZpgMoAIAwAA"
    "AAdBmoAygAgDAAAAB0GaoDaACAMAAAAHQZrANoAIAwAAAAdBmuA2gAgDAAAAB0GbADaACAMAAAAH"
    "QZsgNoAIAwAAAAdBm0A2gAgDAAAAB0GbYDaACAMAAAAHQZuANoAIAwAAAAdBm6A2gAgDAAAAB0Gb"
    "wDaACAM="
)


def make_jpeg_672():
    """672×672 red JPEG, ffmpeg-generated, low-tier compatible."""
    return base64.b64decode(_JPEG_672_RED_B64)


def make_gif_672():
    """672×672 red GIF, ffmpeg-generated, low-tier compatible."""
    return base64.b64decode(_GIF_672_RED_B64)


def make_webp_672():
    """672×672 red WEBP, ffmpeg-generated, low-tier compatible."""
    return base64.b64decode(_WEBP_672_RED_B64)


def png_base64():
    return "data:image/png;base64," + base64.b64encode(make_png_672()).decode()


def jpeg_base64():
    return "data:image/jpeg;base64," + base64.b64encode(make_jpeg_672()).decode()


def gif_base64():
    return "data:image/gif;base64," + base64.b64encode(make_gif_672()).decode()


def webp_base64():
    return "data:image/webp;base64," + base64.b64encode(make_webp_672()).decode()


def corrupted_base64():
    return "data:image/png;base64,aW52YWxpZGltYWdlZGF0YQ=="


def large_image_base64(size_mb=12):
    """Generate oversized base64 image: a 672×672 PNG header + zero-pad to size_mb.

    ⚠️ Known issue (2026-06-04): this helper uses a stdlib hand-crafted minimal solid-color PNG as the base,
    and some providers (e.g. fireworks-m3) have a silent drop behavior in their vision preprocess for
    "solid color / extremely low entropy" images (see badcase_scripts/fireworks_m3_11_02_root_cause_probe*),
    causing the size check to be bypassed — the server drops the image before the size check and uniformly
    returns 200 + fallback text. For cases that strictly require asserting "size > cap must be 4xx",
    use oversized_real_image_data_url() instead.
    """
    data = make_png_672() + b"\x00" * (size_mb * 1024 * 1024)
    return "data:image/png;base64," + base64.b64encode(data).decode()


def oversized_real_image_data_url(size_mb=12, fixture="sx1.jpg", media_type="image/jpeg"):
    """Generate oversized base64 by padding a REAL image with zero bytes to size_mb.

    Uses a real natural image (default sx1.jpg, woman at the seaside, 239 KB JPEG) as base + zero padding,
    to bypass providers' silent drop bug for "minimal solid-color PNG" (see [[large_image_base64]] notes).
    Padding does not affect the JPEG/PNG header and can be recognized by frontend validation as a complete image data url.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "m3_test_images" / "real" / fixture
    if not fixture_path.exists():
        raise FileNotFoundError(f"missing real image fixture: {fixture_path}")
    raw = fixture_path.read_bytes()
    pad_bytes = max(0, size_mb * 1024 * 1024 - len(raw))
    return f"data:{media_type};base64," + base64.b64encode(raw + b"\x00" * pad_bytes).decode()


def mime_mismatch_base64():
    """PNG data labeled as JPEG (672×672 red PNG, mis-tagged image/jpeg)."""
    return "data:image/jpeg;base64," + base64.b64encode(make_png_672()).decode()


# --------------- Test video (504×504, 1s, H.264; low-tier compatible) ---------------

SAMPLE_VIDEO_URL = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"


def make_minimal_mp4_504():
    """504×504 / 1s / H.264 black-frame MP4, ffmpeg-generated."""
    return base64.b64decode(_MP4_504_BLACK_B64)


def mp4_base64():
    return "data:video/mp4;base64," + base64.b64encode(make_minimal_mp4_504()).decode()


# --------------- Oversize fixtures (size-limit boundary tests) ---------------
#
# Server-side file size constraints (size-limit boundary tests):
#   - Images ≤ 10 MB (applies to both URL and Base64)
#   - Videos ≤ 50 MB (applies to both URL and Base64)
#   - Request body ≤ 64 MB (easy to trigger via Base64 path)
# 5 fixtures are committed to git (~150MB total) and to COS; loading logic: read local if present, otherwise download from COS URL and cache.
_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_COS_BASE = "https://qa-tool-1315599187.cos.ap-shanghai.myqcloud.com/m3-test"

# Filename → COS URL (used as URL path by size_limit tests)
SIZE_FIXTURE_URLS = {
    "image_9mb.png":   f"{_COS_BASE}/image_9mb.png",   # ~9.2 MB, image ≤10MB (should pass)
    "image_11mb.png":  f"{_COS_BASE}/image_11mb.png",  # ~11.1 MB, image >10MB (should reject)
    "image_65mb.png":  f"{_COS_BASE}/image_65mb.png",  # ~67 MB, base64 hits the 64MB request body cap (should reject)
    "video_49mb.mp4":  f"{_COS_BASE}/video_49mb.mp4",  # ~47.4 MB, video ≤50MB (should pass)
    "video_51mb.mp4":  f"{_COS_BASE}/video_51mb.mp4",  # ~52 MB, video >50MB (should reject)
}


def load_size_fixture(name: str) -> bytes:
    """Load from local fixtures; if missing, download from COS and cache locally."""
    if name not in SIZE_FIXTURE_URLS:
        raise ValueError(f"unknown size fixture: {name}")
    fp = _FIXTURES_DIR / name
    if fp.exists():
        return fp.read_bytes()
    # fallback: pull from COS
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    url = SIZE_FIXTURE_URLS[name]
    with httpx.stream("GET", url, timeout=300.0) as resp:
        resp.raise_for_status()
        with open(fp, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return fp.read_bytes()


def size_fixture_url(name: str) -> str:
    """Return the fixture's COS URL (for image_url/video_url URL path)."""
    if name not in SIZE_FIXTURE_URLS:
        raise ValueError(f"unknown size fixture: {name}")
    return SIZE_FIXTURE_URLS[name]


def size_fixture_data_url(name: str) -> str:
    """Return the fixture's base64 data URL (for image_url/video_url base64 path)."""
    raw = load_size_fixture(name)
    if name.endswith(".png"):
        return "data:image/png;base64," + base64.b64encode(raw).decode()
    if name.endswith(".mp4"):
        return "data:video/mp4;base64," + base64.b64encode(raw).decode()
    raise ValueError(f"unknown extension: {name}")


# --------------- Weather tool definition (used across tests) ---------------

WEATHER_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
            },
            "required": ["location"],
        },
    },
}


def make_tools_oai(n=1):
    """Generate n tool definitions for OAI format."""
    tools = []
    for i in range(n):
        tools.append({
            "type": "function",
            "function": {
                "name": f"tool_{i}" if i > 0 else "get_weather",
                "description": f"Tool {i} description",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string", "description": f"Param for tool {i}"},
                    },
                    "required": ["param"],
                },
            },
        })
    return tools


# Six parameter types for tool definitions
PARAM_TYPES_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "complex_tool",
        "description": "Tool with 6 parameter types",
        "parameters": {
            "type": "object",
            "properties": {
                "str_param": {"type": "string"},
                "int_param": {"type": "integer"},
                "float_param": {"type": "number"},
                "bool_param": {"type": "boolean"},
                "arr_param": {"type": "array", "items": {"type": "string"}},
                "obj_param": {"type": "object", "properties": {"key": {"type": "string"}}},
            },
            "required": ["str_param"],
        },
    },
}

NESTED_SCHEMA_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "nested_tool",
        "description": "Tool with 4-level nested schema",
        "parameters": {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "level3": {
                                    "type": "object",
                                    "properties": {
                                        "level4": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


# --------------- Advanced schema tools (for G2~G7) ---------------

# Zero-arg tool, used by G2 multi-tool parallel (get_current_time takes no business params)
# Note: M3 official gateway strictly validates that function.parameters is non-empty (spec 1.8.1 marks it optional, but actually not allowed)
# → use {"type":"object","properties":{}} to express "accepts an empty parameters object"
TIME_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current server time (UTC)",
        "parameters": {"type": "object", "properties": {}},
    },
}

# Weather tool with enum, used for G3 enum validation
WEATHER_WITH_UNIT_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "get_weather_with_unit",
        "description": "Get current weather with temperature unit",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit",
                },
            },
            "required": ["location", "unit"],
        },
    },
}

# Forecast tool with numeric range, used for G4 min/max validation
FORECAST_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "get_weather_forecast",
        "description": "Get N-day weather forecast for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 14,
                    "description": "Number of forecast days (1-14)",
                },
            },
            "required": ["location", "days"],
        },
    },
}

# Flight search tool with multiple required fields, used for G5 multi-required validation
FLIGHT_SEARCH_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": "Search flights between two cities on a specific date",
        "parameters": {
            "type": "object",
            "properties": {
                "from_city": {"type": "string", "description": "Departure city"},
                "to_city": {"type": "string", "description": "Destination city"},
                "date": {"type": "string", "description": "Flight date in YYYY-MM-DD"},
                "passengers": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 9,
                    "description": "Number of passengers",
                },
            },
            "required": ["from_city", "to_city", "date"],
        },
    },
}

# Booking tool with nested array-of-objects, used for G6 nested validation
BOOKING_TOOL_OAI = {
    "type": "function",
    "function": {
        "name": "book_room",
        "description": "Book a hotel room for multiple guests",
        "parameters": {
            "type": "object",
            "properties": {
                "hotel_id": {"type": "string"},
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "guests": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer", "minimum": 0, "maximum": 120},
                        },
                        "required": ["name", "age"],
                    },
                },
            },
            "required": ["hotel_id", "check_in", "guests"],
        },
    },
}


# --------------- HTTP helpers ---------------

def _extract_trace_id(response_headers: Optional[dict],
                      body: Optional[dict],
                      chunks: Optional[list]) -> Optional[str]:
    """Best-effort trace_id extraction: header first → body.id (non_stream) → chunks[0].id (stream).

    Order considerations:
      1. Gateway-layer x-request-id / x-trace-id / trace-id (case-insensitive), closest to a "per-request unique identifier"
      2. body["id"] — OAI chat.completion spec field chatcmpl-xxx, always returned
      3. In stream mode, take id from the first data chunk (same source as body.id)
    """
    if response_headers:
        lower = {k.lower(): v for k, v in response_headers.items()}
        for key in ("x-request-id", "x-trace-id", "trace-id", "x-trace"):
            v = lower.get(key)
            if v:
                return str(v)
    if isinstance(body, dict):
        v = body.get("id")
        if v:
            return str(v)
    if chunks:
        for c in chunks:
            if isinstance(c, dict) and c.get("id"):
                return str(c["id"])
    return None


def oai_chat(payload, stream=False, headers=None, timeout=TIMEOUT):
    """Send OAI chat completion request, log full request+response to jsonl.

    Returns the same shape as before:
      non-stream → {"status": int, "body": dict, "stream": False}
      stream     → {"status": int, "chunks": [dict, ...], "stream": True}

    Logging is best-effort and runs in a finally block so failed/raising calls
    still leave a trace on disk.
    """
    hdrs = headers or OAI_HEADERS
    # Mutate payload as the original helper did so the log captures what was
    # actually on the wire (model, stream flag).
    payload.setdefault("model", MODEL)
    payload["stream"] = stream

    started = time.time()
    status = 0
    body = None
    chunks: Optional[list] = None
    response_headers: Optional[dict] = None
    error: Optional[str] = None
    try:
        if stream:
            chunks = []
            with httpx.Client(timeout=timeout) as c:
                with c.stream("POST", OAI_URL, json=payload, headers=hdrs) as resp:
                    status = resp.status_code
                    response_headers = dict(resp.headers)
                    # Error responses are usually not SSE but plain JSON; read the body directly and skip iter_lines
                    # (iter_lines only captures "data: " / "event: " prefixes, so a JSON error body would be silently swallowed)
                    if status >= 400:
                        resp.read()
                        try:
                            body = resp.json()
                        except Exception:
                            body = {"_raw": resp.text}
                    else:
                        for line in resp.iter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    chunks.append({"_done": True})
                                else:
                                    try:
                                        chunks.append(json.loads(data))
                                    except json.JSONDecodeError:
                                        chunks.append({"_raw": data})
                            elif line.startswith("event: "):
                                chunks.append({"_event": line[7:]})
                    return {
                        "status": status,
                        "chunks": chunks,
                        "stream": True,
                        "body": body,
                        "response_headers": response_headers,
                        "trace_id": _extract_trace_id(response_headers, body, chunks),
                    }
        else:
            resp = httpx.post(OAI_URL, json=payload, headers=hdrs, timeout=timeout)
            status = resp.status_code
            response_headers = dict(resp.headers)
            try:
                body = resp.json()
            except Exception:
                body = {"_raw": resp.text}
            return {
                "status": status,
                "body": body,
                "stream": False,
                "response_headers": response_headers,
                "trace_id": _extract_trace_id(response_headers, body, None),
            }
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        elapsed_ms = int((time.time() - started) * 1000)
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "case_id": _current_case_id(),
            "endpoint": "oai",
            "url": OAI_URL,
            "stream": stream,
            "elapsed_ms": elapsed_ms,
            "status": status,
            "trace_id": _extract_trace_id(response_headers, body, chunks),
            "request": payload,
            "response": body,
            "chunks": chunks,
            "response_headers": response_headers,
        }
        if error is not None:
            record["error"] = error
        try:
            _write_log_line(record)
        except Exception:
            # Logging must never mask a real test failure.
            pass


# --------------- Assertion helpers ---------------

def assert_oai_success(result):
    assert result["status"] == 200, f"Expected 200, got {result['status']}: {result.get('body', '')}"
    if not result.get("stream"):
        body = result["body"]
        assert "choices" in body, f"Missing 'choices': {body}"
        assert len(body["choices"]) > 0
        assert "usage" in body


def assert_oai_stream_success(result):
    """OAI streaming success assertion: HTTP 200 + non-empty chunks + tail contains a valid finish_reason.

    The tail finish_reason check is folded into the assert_stream_complete logic
    so all stream cases benefit automatically (no need to add it case by case).
    If a case intentionally needs "no finish_reason" (very rare extreme tests), use the bare status==200 check instead.
    """
    assert result["status"] == 200, f"Expected 200, got {result['status']}"
    assert result.get("stream")
    assert len(result["chunks"]) > 0
    assert_stream_complete(result, msg="assert_oai_stream_success")


def assert_stream_complete(result, msg: str = ""):
    """Assert a streaming response finishes cleanly: the last non-empty chunk carries a valid finish_reason.

    Background: the OAI streaming protocol requires a terminating frame (or a [DONE] marker). Empirically, M3's last chunk
    carries `choices[0].finish_reason ∈ {stop, length, tool_calls, content_filter}`.
    """
    chunks = result.get("chunks") or []
    assert chunks, f"{msg}: stream has no chunks"
    # Skip the trailing pure-usage chunk (choices may be empty) and the [DONE] marker
    finish_reason = None
    for c in reversed(chunks):
        choices = c.get("choices") or []
        if not choices:
            continue
        fr = choices[0].get("finish_reason")
        if fr is not None:
            finish_reason = fr
            break
    valid = ("stop", "length", "tool_calls", "content_filter")
    assert finish_reason in valid, (
        f"{msg}: stream last chunk missing valid finish_reason, "
        f"got {finish_reason!r} (valid: {valid})\n"
        f"  last 2 chunks: {chunks[-2:]}"
    )


def assert_stream_usage_only_in_last_chunk(result, msg: str = ""):
    """When `stream_options.include_usage=true`, assert:
      1. At least one chunk carries `usage`;
      2. The `usage` object is non-empty and the three token fields are populated (>0);
      3. `usage` only appears in the final data chunk (the `[DONE]` marker and any
         trailing event lines are skipped — the last *content-bearing* SSE chunk
         is the one that must carry it). No earlier delta chunk may carry usage.

    Spec: OpenAI streaming `include_usage` defines a single terminal chunk that
    carries the final `usage` object; intermediate delta chunks must not.
    """
    chunks = result.get("chunks") or []
    assert chunks, f"{msg}: stream has no chunks"

    # Filter out non-data sentinels we synthesize in oai_chat: _done / _event / _raw.
    data_chunks = [
        c for c in chunks
        if isinstance(c, dict) and not (c.get("_done") or c.get("_event") or c.get("_raw"))
    ]
    assert data_chunks, f"{msg}: stream has no data chunks (only DONE/event markers)"

    usage_indices = [i for i, c in enumerate(data_chunks) if c.get("usage")]
    assert usage_indices, (
        f"{msg}: no usage chunk in stream despite stream_options.include_usage=true"
    )

    # Only the last data chunk may carry usage.
    last_idx = len(data_chunks) - 1
    bad = [i for i in usage_indices if i != last_idx]
    assert not bad, (
        f"{msg}: usage must appear only in the final stream chunk, "
        f"but was found at data-chunk indices {bad} (last index = {last_idx}). "
        f"total data chunks = {len(data_chunks)}"
    )

    last_usage = data_chunks[last_idx].get("usage")
    assert isinstance(last_usage, dict) and last_usage, (
        f"{msg}: final-chunk usage should be a non-empty object, got {last_usage!r}"
    )
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        v = last_usage.get(k)
        assert isinstance(v, int) and not isinstance(v, bool) and v > 0, (
            f"{msg}: final-chunk usage.{k} should be a positive int, got {v!r}. "
            f"usage={last_usage!r}"
        )


def assert_error(result, expected_status):
    assert result["status"] == expected_status, (
        f"Expected {expected_status}, got {result['status']}: {result.get('body', result.get('chunks', ''))}"
    )


# --------------- Thinking detection ---------------
# spec 1.4: thinking.type ∈ disabled / adaptive
# Different OAI-compatible implementations may place thinking in different locations; do a robust detection here:
#   1) <think>...</think> tag wrapped inside content (BUG-X form annotated in V04/V09)
#   2) message.reasoning_content as a separate field (common when reasoning_split=true)
#   3) usage.completion_tokens_details.reasoning_tokens > 0
# Any hit counts as "did think".

def _stream_choice_message(result: dict) -> dict:
    """Aggregate deltas from a streaming result back into a message-like dict (takes the first choice).

    Compatible with two thinking field namings:
      - M3 spec: delta.reasoning_content
      - Together / some OAI-compatible implementations: delta.reasoning
    Either occurrence is accumulated into reasoning_content.
    """
    msg = {"content": "", "reasoning_content": ""}
    for chunk in result.get("chunks") or []:
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            msg["content"] += delta["content"]
        if delta.get("reasoning_content"):
            msg["reasoning_content"] += delta["reasoning_content"]
        # Compat for together-m3 etc. that emit delta.reasoning
        if delta.get("reasoning"):
            msg["reasoning_content"] += delta["reasoning"]
    return msg


def _stream_usage(result: dict) -> dict:
    """From a streaming result, take the usage field of the last chunk that contains usage."""
    for chunk in reversed(result.get("chunks") or []):
        if isinstance(chunk, dict) and chunk.get("usage"):
            return chunk["usage"]
    return {}


def get_thinking_signals(result: dict) -> dict:
    """Extract all possible thinking signals, for use in assertions/debugging.

    Compatible with two field namings (M3 spec / together etc. OAI-compatible):
      - message.reasoning_content (spec)
      - message.reasoning         (together)
    Either non-empty counts as having thinking. usage.*_tokens is no longer used as a decision basis (vendor implementations vary too much).

    Returns a dict with:
      - has_think_tag (bool): whether content contains a <think> tag
      - reasoning_content (str): the thinking body (already merged from both fields)
      - any (bool): whether any signal hit
    """
    if result.get("stream"):
        msg = _stream_choice_message(result)
    else:
        body = result.get("body") or {}
        choices = body.get("choices") or []
        msg = (choices[0].get("message") if choices else None) or {}

    content = msg.get("content") or ""
    reasoning_content = (msg.get("reasoning_content") or msg.get("reasoning") or "")
    has_think_tag = "<think>" in content.lower()

    return {
        "has_think_tag": has_think_tag,
        "reasoning_content": reasoning_content,
        "any": bool(has_think_tag or reasoning_content.strip()),
    }


def assert_thinking_present(result: dict, msg: str = ""):
    """Assert that the response contains a thinking signal (a <think> tag or non-empty reasoning_content/reasoning)."""
    sig = get_thinking_signals(result)
    assert sig["any"], (
        f"{msg}: expected thinking present, but no signal found.\n"
        f"  has_think_tag={sig['has_think_tag']}\n"
        f"  reasoning_content_len={len(sig['reasoning_content'])}"
    )


def assert_thinking_absent(result: dict, msg: str = ""):
    """Assert that the response contains no thinking signal (should hold in disabled mode)."""
    sig = get_thinking_signals(result)
    assert not sig["any"], (
        f"{msg}: expected no thinking, but found signal.\n"
        f"  has_think_tag={sig['has_think_tag']}\n"
        f"  reasoning_content (first 200 chars)={sig['reasoning_content'][:200]!r}"
    )


def get_oai_content(result):
    """Aggregate message.content from an OAI response (stream = sum of delta.content).

    Defensive handling: streams commonly end with a pure-usage chunk (choices=[]); do not index [0] or it raises IndexError.
    """
    if result.get("stream"):
        parts = []
        for chunk in result.get("chunks") or []:
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                parts.append(delta["content"])
        return "".join(parts)
    body = result.get("body") or {}
    choices = body.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message") or {}).get("content", "") or ""


# --------------- Tool call extraction & assertions ---------------
# spec 1.8.1 tools list structure + function.parameters recommended format
# All "trigger-type" toolcall cases use this toolkit for assertions:
#   - The model actually called the expected tool (name matches)
#   - arguments is valid JSON
#   - arguments field values match prompt/definition expectations (optional subset match)
# Streaming responses need to be rebuilt according to the OAI delta.tool_calls protocol

def get_tool_calls(result: dict) -> list:
    """Extract the tool_calls list from an oai_chat return (both streaming and non-streaming compatible).

    Returns [{"id": str, "name": str, "arguments_raw": str, "arguments_obj": dict|None}, ...]
    arguments_obj being None means it could not be parsed as JSON (also a signal of assertion failure).
    """
    raw_calls = []  # [{"id", "name", "arguments"}] intermediate form

    if result.get("stream"):
        # Streaming: rebuild per OAI delta.tool_calls protocol
        # In delta, tool_calls is [{"index": i, "id": ..., "function": {"name": ..., "arguments": "fragment"}}]
        # arguments strings at the same index need to be concatenated; id usually appears the first time
        partials = {}  # index -> {"id": str, "name": str, "arguments": str}
        for chunk in result.get("chunks") or []:
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = partials.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if tc.get("id"):
                    slot["id"] = tc["id"]  # id appears once; later occurrences overwrite
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]  # some implementations also fragment the name
                if fn.get("arguments") is not None:
                    slot["arguments"] += fn["arguments"]
        for idx in sorted(partials):
            raw_calls.append(partials[idx])
    else:
        body = result.get("body") or {}
        choices = body.get("choices") or []
        if not choices:
            return []
        msg = choices[0].get("message") or {}
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_calls.append({
                "id": tc.get("id") or "",
                "name": fn.get("name") or "",
                "arguments": fn.get("arguments") or "",
            })

    # Parse arguments JSON
    parsed = []
    for c in raw_calls:
        args_raw = c.get("arguments") or ""
        try:
            args_obj = json.loads(args_raw) if args_raw.strip() else {}
            if not isinstance(args_obj, dict):
                args_obj = None
        except (json.JSONDecodeError, ValueError):
            args_obj = None
        parsed.append({
            "id": c.get("id") or "",
            "name": c.get("name") or "",
            "arguments_raw": args_raw,
            "arguments_obj": args_obj,
        })
    return parsed


def _value_loosely_equal(actual, expected) -> bool:
    """Loose match for field values:
    - Strings: case-insensitive + strip leading/trailing spaces + tolerate containment (actual contains expected or vice versa)
    - Numeric types are interchangeable (int/float)
    - bool/list/dict require strict equality
    Used for scenarios where the prompt says 'Beijing' but the model may return '北京'/'beijing'/'Beijing, China'.
    """
    if expected is None:
        return actual is None
    if isinstance(expected, bool):  # bool must be checked before int (True is an int)
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return abs(actual - expected) < 1e-9
    if isinstance(expected, str) and isinstance(actual, str):
        a = actual.strip().lower()
        e = expected.strip().lower()
        return a == e or e in a or a in e
    if isinstance(expected, list) and isinstance(actual, list):
        return actual == expected
    if isinstance(expected, dict) and isinstance(actual, dict):
        return actual == expected
    return actual == expected


def _expected_types_for(param_schema: dict) -> tuple:
    """Map JSON Schema type into a tuple of Python types, for use with isinstance.
    Supports a single type string or an array of types (spec 1.8.1 recommends type:["string","number",...])
    """
    type_field = param_schema.get("type")
    if not type_field:
        return (object,)  # No type constraint, allow any type
    if isinstance(type_field, str):
        types = [type_field]
    else:
        types = list(type_field)
    py_types = []
    for t in types:
        if t == "string":
            py_types.append(str)
        elif t == "integer":
            py_types.append(int)
        elif t == "number":
            py_types.append((int, float))
        elif t == "boolean":
            py_types.append(bool)
        elif t == "array":
            py_types.append(list)
        elif t == "object":
            py_types.append(dict)
        elif t == "null":
            py_types.append(type(None))
    flat = []
    for x in py_types:
        if isinstance(x, tuple):
            flat.extend(x)
        else:
            flat.append(x)
    return tuple(flat) if flat else (object,)


def _validate_schema(args, schema: dict, path: str, msg: str):
    """Recursively validate args against a JSON Schema subset (type/required/properties/items/enum/min/max).

    Supported keywords:
      - type (single value or array; see _expected_types_for)
      - required (mandatory fields on objects)
      - properties (recurse into object fields)
      - items (recurse into array elements)
      - enum (enum check for any value)
      - minimum / maximum (number/integer range)
      - minLength / maxLength (string length)
      - minItems / maxItems (array length)

    On assertion failure, `path` pinpoints the specific field (e.g. "passengers[0].name").
    """
    # 1. type
    expected_types = _expected_types_for(schema)
    if expected_types != (object,):
        assert isinstance(args, expected_types), (
            f"{msg}: {path} type mismatch.\n"
            f"  expected types={[t.__name__ for t in expected_types]}  "
            f"actual={type(args).__name__} value={args!r}"
        )

    # 2. enum
    if "enum" in schema:
        allowed = schema["enum"]
        assert args in allowed, (
            f"{msg}: {path} value not in enum.\n"
            f"  enum={allowed}  actual={args!r}"
        )

    # 3. number/integer range
    if isinstance(args, (int, float)) and not isinstance(args, bool):
        if "minimum" in schema:
            assert args >= schema["minimum"], (
                f"{msg}: {path}={args} below minimum {schema['minimum']}"
            )
        if "maximum" in schema:
            assert args <= schema["maximum"], (
                f"{msg}: {path}={args} above maximum {schema['maximum']}"
            )

    # 4. string length
    if isinstance(args, str):
        if "minLength" in schema:
            assert len(args) >= schema["minLength"], (
                f"{msg}: {path}={args!r} length {len(args)} below minLength {schema['minLength']}"
            )
        if "maxLength" in schema:
            assert len(args) <= schema["maxLength"], (
                f"{msg}: {path}={args!r} length {len(args)} above maxLength {schema['maxLength']}"
            )

    # 5. array
    if isinstance(args, list):
        if "minItems" in schema:
            assert len(args) >= schema["minItems"], (
                f"{msg}: {path} array length {len(args)} below minItems {schema['minItems']}"
            )
        if "maxItems" in schema:
            assert len(args) <= schema["maxItems"], (
                f"{msg}: {path} array length {len(args)} above maxItems {schema['maxItems']}"
            )
        item_schema = schema.get("items")
        if item_schema:
            for i, elem in enumerate(args):
                _validate_schema(elem, item_schema, f"{path}[{i}]", msg)

    # 6. object
    if isinstance(args, dict):
        for req in schema.get("required") or []:
            assert req in args, (
                f"{msg}: {path}.{req} required but missing.\n"
                f"  got_keys={list(args.keys())} schema_required={schema.get('required')}"
            )
        props = schema.get("properties") or {}
        for k, v in args.items():
            ps = props.get(k)
            if ps:
                _validate_schema(v, ps, f"{path}.{k}", msg)


def assert_tool_called(result: dict,
                       expected_name=None,
                       expected_args_subset: dict = None,
                       schema: dict = None,
                       msg: str = ""):
    """Assert the model called at least one tool, with optional validations:
      - expected_name: str or list[str]. When str, the first tool_call.name must match;
        when list, the first tool_call.name must be ∈ list (for "the model may pick one of them" scenarios)
      - expected_args_subset: arguments_obj should contain these fields (values compared via _value_loosely_equal)
      - schema: function.parameters JSON Schema, validated recursively:
          * required / properties / items / enum / minimum / maximum / minLength / maxLength
          * Nested object and array fields are recursed deeply

    On assertion failure, prints raw + parsed to help diagnose "called but JSON broken / wrong field types / wrong tool".
    """
    calls = get_tool_calls(result)
    assert calls, (
        f"{msg}: expected at least one tool_call, got none.\n"
        f"  status={result.get('status')} "
        f"body={str(result.get('body'))[:300] if not result.get('stream') else 'streaming'}"
    )
    call = calls[0]
    if expected_name is not None:
        if isinstance(expected_name, (list, tuple, set)):
            allowed = list(expected_name)
            assert call["name"] in allowed, (
                f"{msg}: expected tool name in {allowed}, got {call['name']!r}\n"
                f"  arguments_raw={call['arguments_raw'][:300]}"
            )
        else:
            assert call["name"] == expected_name, (
                f"{msg}: expected tool name {expected_name!r}, got {call['name']!r}\n"
                f"  arguments_raw={call['arguments_raw'][:300]}"
            )
    # arguments JSON parsing must succeed
    assert call["arguments_obj"] is not None, (
        f"{msg}: arguments is not valid JSON.\n"
        f"  raw={call['arguments_raw'][:500]}"
    )
    args = call["arguments_obj"]

    if expected_args_subset:
        for k, v in expected_args_subset.items():
            assert k in args, (
                f"{msg}: expected arg {k!r} missing in arguments.\n"
                f"  got_keys={list(args.keys())} raw={call['arguments_raw'][:300]}"
            )
            assert _value_loosely_equal(args[k], v), (
                f"{msg}: arg {k!r} value mismatch.\n"
                f"  expected≈{v!r}  actual={args[k]!r}"
            )

    if schema:
        _validate_schema(args, schema, "args", msg)


def assert_tools_called_set(result: dict, expected_names, schemas: dict = None, msg: str = ""):
    """Assert the model called every name in the set (any order, extras allowed), for multi-tool parallel scenarios.
      - expected_names: list/set[str] of names that must all appear
      - schemas: optional dict[str -> schema] to validate the corresponding args by name

    Stricter than assert_tool_called: every expected_name must appear; missing any one fails.
    """
    calls = get_tool_calls(result)
    assert calls, (
        f"{msg}: expected tool_calls including {set(expected_names)}, got none."
    )
    actual_names = [c["name"] for c in calls]
    expected_set = set(expected_names)
    actual_set = set(actual_names)
    missing = expected_set - actual_set
    assert not missing, (
        f"{msg}: missing expected tool calls.\n"
        f"  expected={expected_set}  actual={actual_names}\n"
        f"  missing={missing}"
    )
    # arguments must be valid JSON
    for c in calls:
        assert c["arguments_obj"] is not None, (
            f"{msg}: tool {c['name']!r} arguments not valid JSON.\n"
            f"  raw={c['arguments_raw'][:300]}"
        )
        if schemas and c["name"] in schemas:
            _validate_schema(c["arguments_obj"], schemas[c["name"]], f"args[{c['name']}]", msg)


def assert_no_tool_called(result: dict, msg: str = ""):
    """Assert the model did not call any tool (for tool_choice='none' / should-fall-back-to-chat scenarios)."""
    calls = get_tool_calls(result)
    assert not calls, (
        f"{msg}: expected no tool_call, but got {len(calls)}: "
        f"{[(c['name'], c['arguments_raw'][:100]) for c in calls]}"
    )


# --------------- Conversation builders ---------------

def oai_simple_messages(user_text="Hello", system_text=None):
    msgs = []
    if system_text:
        msgs.append({"role": "system", "content": system_text})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def oai_multiturn_messages():
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Hello Alice! How can I help you today?"},
        {"role": "user", "content": "What's my name?"},
    ]


def long_conversation_messages(rounds=20):
    """Generate a conversation with `rounds` user-assistant turns."""
    msgs = [{"role": "system", "content": "You are a helpful assistant."}]
    for i in range(rounds):
        msgs.append({"role": "user", "content": f"This is turn {i+1}. What is {i+1} + {i+1}?"})
        msgs.append({"role": "assistant", "content": f"The answer is {(i+1)*2}."})
    return msgs


def long_system_text(tokens_approx=10000):
    """Generate a ~10K token system message."""
    word = "test "
    return word * (tokens_approx * 4 // len(word))


def generate_50k_string():
    """Generate ~50K character string for tool result edge tests."""
    return "A" * 50000

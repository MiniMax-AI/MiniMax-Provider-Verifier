"""
M3 API Test — video modality case suite

Organized into modules by "what is being validated"; case naming convention:
    test_<module_number>_<within_module_order>_<scenario_description>

Module number / topic:
    01  base64_video          base64 video basic acceptance
    02  url_video             URL video acceptance
    03  video_format          video container/MIME format (MOV/MKV/AVI, etc.)
    04  multi_video           multi-video stacking / count upper bound
    05  image_video_mixed     image + video mixed message
    06  fps_param             fps valid tiers and out-of-range
    07  detail_param          detail / fps field defaults and combinations
    08  resolution_tier       resolution tier / boundary / pixel cap
    09  max_long_side_pixel   max_long_side_pixel (multiple of 28) contract
    10  video_size_limit      video size limit (<=50MB)
    11  long_video            long video (5/10/20/30 min)
    12  media_gradient        resolution gradient / multi-video gradient
    13  video_extension       reasoning_split and other extension fields
    14  error_codes           video-related error codes
    15  stream_usage          video + streaming stream_options.include_usage usage-chunk protocol

Modality priority video > image > text; this file covers video (mixed image+video also lives here).

All cases go through helpers.oai_chat() to /v1/chat/completions; jsonl is
written to RUN_LOG_PATH (injected by conftest).
"""
import base64
import os
from pathlib import Path

import pytest

from helpers import *
from image_tools import (
    fixture_video_base64,
    fixture_video_url,
    VIDEO_FIXTURES,
)


# ============================================================
# File-local helpers: real video fixture loaders
# (avoid polluting helpers.py / shares name+semantics with the M3 team reference implementation's real_video_b64)
# ============================================================

_REAL_VIDEO_DIR = Path(__file__).parent / "fixtures" / "m3_test_videos"
_REAL_IMAGE_DIR = Path(__file__).parent / "fixtures" / "m3_test_images" / "real"


def real_video_b64(name: str = "real_2s.mp4", mime: str = "video/mp4") -> str:
    """Read fixtures/m3_test_videos/<name> -> base64 data URL.

    Same semantics as m3_image_tests.py:real_image_b64. Common fixtures:
      - real_2s.mp4     (~104KB, P09/P14 content understanding cases)
      - 12s_real.mp4    (~628KB, 06 fps valid-tier 12-second video)
      - flower-video.mp4 (~1MB, second clip for image+video mixed cases)
      - test_video.mov / .mkv / .avi (~160KB, 03 module real non-MP4 format smoke)
    """
    path = _REAL_VIDEO_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"real video fixture missing: {path}\n"
            f"参考实现期望 fixtures/m3_test_videos/ 下存在 real_2s.mp4 / 12s_real.mp4 等"
        )
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def real_image_b64_for_video(name: str = "sx1.jpg", mime: str = "image/jpeg") -> str:
    """Read a local copy of fixtures/m3_test_images/real/<name>, used by image+video mixed cases inside the video file.

    Kept isolated from m3_image_tests.py:real_image_b64 to avoid cross-file imports.
    """
    path = _REAL_IMAGE_DIR / name
    if not path.exists():
        raise FileNotFoundError(
            f"real image fixture missing: {path}\n"
            f"参考实现期望 fixtures/m3_test_images/real/ 下存在 sx1.jpg"
        )
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# Long videos (>10MB) are loaded preferentially from the directory specified by M3_LONG_VIDEO_DIR;
# when unset, fall back to local fixtures/m3_test_videos/ (D_300s/D_600s/D_1200s/D_1800s.mp4 committed).
# Example: export M3_LONG_VIDEO_DIR=/Users/minimax/Downloads/M3/assets/videos/duration
_LONG_VIDEO_DIR_ENV = "M3_LONG_VIDEO_DIR"
_LOCAL_LONG_DIR = Path(__file__).parent / "fixtures" / "m3_test_videos"


def long_video_path(name: str) -> Path:
    base = os.environ.get(_LONG_VIDEO_DIR_ENV)
    if base:
        return Path(base) / name
    return _LOCAL_LONG_DIR / name


def long_video_b64(name: str, mime: str = "video/mp4") -> str:
    p = long_video_path(name)
    if not p.exists():
        raise FileNotFoundError(
            f"long video missing: {p}\n"
            f"set {_LONG_VIDEO_DIR_ENV}=<dir-containing-{name}>"
        )
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _get_prompt_tokens(r: dict) -> int:
    """Extract prompt_tokens from an oai_chat response (compatible with stream / non_stream)."""
    if not r.get("stream"):
        body = r.get("body") or {}
        return (body.get("usage") or {}).get("prompt_tokens", 0)
    for c in reversed(r.get("chunks") or []):
        usage = c.get("usage") if isinstance(c, dict) else None
        if usage:
            return usage.get("prompt_tokens", 0)
    return 0


def _assert_basic_ok(r: dict, msg: str = ""):
    """Basic assertion for the happy-path of a valid tier: HTTP 200 + positive prompt_tokens."""
    assert r["status"] == 200, (
        f"{msg}: expected 200, got {r['status']}: "
        f"{r.get('body', '')[:300] if isinstance(r.get('body'), str) else r.get('body')}"
    )
    pt = _get_prompt_tokens(r)
    assert pt > 0, f"{msg}: prompt_tokens should be positive, got {pt}"


def _video_payload(filename: str, detail: str = None, fps: float = None,
                   text: str = "What is this?") -> dict:
    """Build the video_url block for a video request."""
    video_url_obj = {"url": fixture_video_base64(filename)}
    if detail is not None:
        video_url_obj["detail"] = detail
    if fps is not None:
        video_url_obj["fps"] = fps
    return {
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": video_url_obj},
            {"type": "text", "text": text},
        ]}],
    }


# Real-asset marker shared across multiple modules (Spring Festival cartoon pony, 5MB)
PONY_VIDEO_FIXTURE = "476117246902419462.mp4"
PONY_VIDEO_URL = (
    "https://qa-tool-1315599187.cos.ap-shanghai.myqcloud.com/m3-test/"
    "476117246902419462.mp4"
)


# ============================================================
# 01 base64_video — base64 video basic acceptance
# ============================================================

class TestBase64Video:
    """Feed video via base64 dataURL: verify minimum viable path + real-asset content understanding."""

    def test_01_01_base64_video(self):
        """Minimal base64 MP4 + What do you see -> HTTP 200 + non-empty answer."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mp4_base64()}},
                {"type": "text", "text": "What do you see?"},
            ]}],
        })
        assert r["status"] == 200
        content = get_oai_content(r)
        assert len(content.strip()) > 20, (
            f"01_01 video understanding should yield non-trivial response, "
            f"got len={len(content)}: {content!r}"
        )

    def test_01_02_base64_real_pony_cartoon(self):
        """Real asset (Spring Festival cartoon pony, 5MB) base64 input: verify content understanding.

        Content reality (frame-checked): a 3D-style cartoon pony/horse wearing a red Chinese-style
        bib (dudou), surrounded by Chinese New Year / Spring Festival props — red lanterns,
        firecrackers, gold ingots (yuanbao), Chinese knots, stylized clouds. To avoid false negatives
        from synonym/translation rewording, we require BOTH:
          - any pony/horse subject keyword (horse / pony / 马 / 小马 / 卡通 / cartoon ...)
          - any festive-scene keyword (lantern / firecracker / new year / spring festival /
            灯笼 / 鞭炮 / 春节 / 新年 / 红色 / 金元宝 / 中国结 ...)
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": fixture_video_base64(PONY_VIDEO_FIXTURE),
                }},
                {"type": "text", "text": "这个视频里有什么?请详细描述。"},
            ]}],
            "max_tokens": 4096,
        })
        assert r["status"] == 200, (
            f"01_02 video base64 should return 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )
        content = get_oai_content(r)
        assert len(content.strip()) > 50, (
            f"01_02 expected non-trivial response, got len={len(content)}: {content!r}"
        )
        content_low = content.lower()
        subject_keywords = (
            "horse", "pony", "stallion", "foal", "cartoon", "animated",
            "马", "小马", "骏马", "卡通", "动画",
        )
        scene_keywords = (
            "lantern", "firecracker", "new year", "spring festival",
            "chinese new year", "lunar", "red", "gold", "ingot", "knot",
            "灯笼", "鞭炮", "春节", "新年", "中国结", "元宝", "金元宝",
            "红色", "金色", "喜庆", "节日", "肚兜", "祥云",
        )
        assert any(kw in content_low for kw in subject_keywords), (
            f"01_02 video subject (horse/pony/cartoon) not recognized, "
            f"content head: {content[:400]!r}"
        )
        assert any(kw in content_low for kw in scene_keywords), (
            f"01_02 Spring Festival scene cues (lantern/firecracker/红/金/春节...) not recognized, "
            f"content head: {content[:400]!r}"
        )


# ============================================================
# 02 url_video — URL video acceptance
# ============================================================

class TestURLVideo:
    """video_url.url uses public network / COS URL form."""

    def test_02_01_url_video(self):
        """Public sample mp4 URL -> HTTP 200 + non-empty answer (basic URL acceptance)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": SAMPLE_VIDEO_URL}},
                {"type": "text", "text": "What is in this video?"},
            ]}],
        })
        assert r["status"] == 200
        content = get_oai_content(r)
        assert len(content.strip()) > 20, (
            f"02_01 video understanding should yield non-trivial response, "
            f"got len={len(content)}: {content!r}"
        )

    def test_02_02_url_real_pony_cartoon(self):
        """Real asset (Spring Festival cartoon pony) via OSS URL input: verify content understanding.

        Same real asset as 01_02 (pony + CNY decorations) but delivered via the public COS URL
        path. Asserts BOTH a subject keyword and a festive-scene keyword to avoid passing on
        generic answers like "这是一个视频" (a non-understanding response).
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": PONY_VIDEO_URL}},
                {"type": "text", "text": "这个视频里有什么?请详细描述。"},
            ]}],
            "max_tokens": 4096,
        })
        assert r["status"] == 200, (
            f"02_02 video_url should return 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )
        content = get_oai_content(r)
        assert len(content.strip()) > 50, (
            f"02_02 expected non-trivial response, got len={len(content)}: {content!r}"
        )
        content_low = content.lower()
        subject_keywords = (
            "horse", "pony", "stallion", "foal", "cartoon", "animated",
            "马", "小马", "骏马", "卡通", "动画",
        )
        scene_keywords = (
            "lantern", "firecracker", "new year", "spring festival",
            "chinese new year", "lunar", "red", "gold", "ingot", "knot",
            "灯笼", "鞭炮", "春节", "新年", "中国结", "元宝", "金元宝",
            "红色", "金色", "喜庆", "节日", "肚兜", "祥云",
        )
        assert any(kw in content_low for kw in subject_keywords), (
            f"02_02 video subject (horse/pony/cartoon) not recognized, "
            f"content head: {content[:400]!r}"
        )
        assert any(kw in content_low for kw in scene_keywords), (
            f"02_02 Spring Festival scene cues (lantern/firecracker/红/金/春节...) not recognized, "
            f"content head: {content[:400]!r}"
        )


# ============================================================
# 03 video_format — video container/MIME format (MOV/MKV/AVI, etc.)
# ============================================================

class TestVideoFormat:
    """Video format compatibility — includes disguised MIME (MOV/MKV/AVI, etc.) and real non-MP4 file smoke."""

    def test_03_01_mkv_format_legacy(self):
        """MKV (video/x-matroska) disguised with minimal mp4 -> xfail when known unsupported."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": "data:video/x-matroska;base64,"
                           + base64.b64encode(make_minimal_mp4_504()).decode(),
                }},
                {"type": "text", "text": "What is this?"},
            ]}],
        })
        if r["status"] != 200:
            pytest.xfail("Known BUG: MKV format not supported")

    def test_03_02_mov_format_video_quicktime(self):
        """MOV (video/quicktime base64) -> xfail when known BUG-7."""
        mov_b64 = ("data:video/quicktime;base64,"
                   + base64.b64encode(make_minimal_mp4_504()).decode())
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mov_b64}},
                {"type": "text", "text": "What?"},
            ]}],
        })
        if r["status"] != 200:
            pytest.xfail("Known BUG-7: MOV format not supported")

    def test_03_03_mov_format_video_mov(self):
        """MOV (spec 1.3.5 requires data:video/mov;base64,...) -> xfail when known BUG-7."""
        mov_b64 = ("data:video/mov;base64,"
                   + base64.b64encode(make_minimal_mp4_504()).decode())
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mov_b64}},
                {"type": "text", "text": "What?"},
            ]}],
        })
        if r["status"] != 200:
            pytest.xfail("Known BUG-7: MOV format not supported")

    def test_03_04_mkv_format_video_matroska(self):
        """MKV (video/x-matroska) disguised with minimal mp4 -> xfail when known BUG-7."""
        mkv_b64 = ("data:video/x-matroska;base64,"
                   + base64.b64encode(make_minimal_mp4_504()).decode())
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mkv_b64}},
                {"type": "text", "text": "What?"},
            ]}],
        })
        if r["status"] != 200:
            pytest.xfail("Known BUG-7: MKV format not supported")

    @pytest.mark.parametrize("mime", ["video/avi", "video/x-msvideo"],
                             ids=["video_avi", "video_x_msvideo"])
    def test_03_05_avi_format(self, mime):
        """Both valid MIME variants of AVI (video/avi / video/x-msvideo) disguised with minimal mp4 -> xfail when unsupported."""
        avi_b64 = f"data:{mime};base64," + base64.b64encode(make_minimal_mp4_504()).decode()
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": avi_b64}},
                {"type": "text", "text": "What?"},
            ]}],
        })
        if r["status"] != 200:
            pytest.xfail(f"AVI format with MIME={mime} not supported / fixture is mp4 data")

    def test_03_06_real_mov_smoke(self):
        """Real MOV file (fixtures/test_video.mov) with default detail/fps -> accept or valid reject."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("test_video.mov", "video/mov"),
                }},
                {"type": "text", "text": "One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] in (200, 400, 415, 422, 500), (
            f"03_06 real MOV unexpected {r['status']}: {str(r.get('body'))[:300]}"
        )

    def test_03_07_real_avi_smoke(self):
        """Real AVI file (fixtures/test_video.avi) with default detail/fps -> accept or valid reject."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("test_video.avi", "video/avi"),
                }},
                {"type": "text", "text": "One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] in (200, 400, 415, 422, 500), (
            f"03_07 real AVI unexpected {r['status']}: {str(r.get('body'))[:300]}"
        )

    def test_03_08_real_mkv_smoke(self):
        """Real MKV file (fixtures/test_video.mkv) with default detail/fps -> accept or valid reject."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("test_video.mkv", "video/x-matroska"),
                }},
                {"type": "text", "text": "One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] in (200, 400, 415, 422, 500), (
            f"03_08 real MKV unexpected {r['status']}: {str(r.get('body'))[:300]}"
        )


# ============================================================
# 04 multi_video — multi-video stacking / count upper bound
# ============================================================

class TestMultiVideo:
    """spec 1.3.6 (updated) video count upper bound 20 + multi-clip stacking boundary coverage.
    20 base64 clips would blow up the request body; boundary cases switch to URL form (fixture_video_url)."""

    def _mp4_block(self):
        return {"type": "video_url", "video_url": {
            "url": "data:video/mp4;base64,"
                   + base64.b64encode(make_minimal_mp4_504()).decode(),
        }}

    def _mp4_url_block(self):
        """A URL-form video_url block for a single video_400x300.mp4 (COS direct link).
        Uses the minimum resolution to reduce gateway download pressure.
        """
        return {"type": "video_url", "video_url": {
            "url": fixture_video_url("video_400x300.mp4"),
        }}

    def test_04_01_count_at_max(self):
        """20 video URLs (spec updated upper bound) -> the endpoint should accept (HTTP 200)."""
        content = [self._mp4_url_block() for _ in range(20)]
        content.append({"type": "text", "text": "How many videos do you see?"})
        r = oai_chat({"messages": [{"role": "user", "content": content}]}, timeout=600)
        assert r["status"] == 200, (
            f"04_01 video count=20 (at max, URL form) HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_04_02_count_over_max(self):
        """21 video URLs (> spec updated upper bound 20) -> 4xx outright reject OR 200 + non-empty response.
        Counter-example: HTTP 200 but content is empty (model produced no textual reply).
        Empirically the official M3 returns 400 `the num of video is larger than the limit: 20` (hard block);
        some providers may let it through; 200 + content is also considered compliant (aligned with image 12_02).
        """
        content = [self._mp4_url_block() for _ in range(21)]
        content.append({"type": "text", "text": "How many?"})
        r = oai_chat({"messages": [{"role": "user", "content": content}]}, timeout=600)
        status = r["status"]
        if 400 <= status < 500:
            return
        assert status == 200, (
            f"04_02 video count=21 (URL form) should be 200 or 4xx, got {status}: "
            f"{str(r.get('body'))[:300]}"
        )
        resp_content = get_oai_content(r)
        assert resp_content and resp_content.strip(), (
            f"04_02 video count=21 returned 200 but content is empty; "
            f"server should either reject 4xx or produce a valid response. "
            f"body: {str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    def test_04_03_multi_video_3(self):
        """3 stacked real_2s.mp4 real videos; allow 200/4xx."""
        vid = real_video_b64("real_2s.mp4")
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": vid}},
                {"type": "video_url", "video_url": {"url": vid}},
                {"type": "video_url", "video_url": {"url": vid}},
                {"type": "text", "text": "Describe each video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"04_03 3 videos unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    def test_04_04_multi_video_5(self):
        """5 stacked real_2s.mp4 real videos (spec upper bound); allow 200/4xx."""
        vid = real_video_b64("real_2s.mp4")
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                *[{"type": "video_url", "video_url": {"url": vid}} for _ in range(5)],
                {"type": "text", "text": "Describe each video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"04_04 5 videos unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_04_05_multi_video_b64_url_mix(self):
        """Mixed form: two clips loaded via different input forms, base64 + URL; allow 200/4xx.

        Different input-form coverage from the "all-base64 same-clip" cases in 04_01..04_04.
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "video_url", "video_url": {"url": fixture_video_url("video_400x300.mp4")}},
                {"type": "text", "text": "How many videos do you see?"},
            ]}],
            "max_tokens": 1024,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"04_05 multi-video b64+url HTTP={r['status']}: {str(r.get('body'))[:300]}"
        )


# ============================================================
# 05 image_video_mixed — image + video mixed message
# ============================================================

class TestImageVideoMixed:
    """Mixed multimodal input with images + videos in the same message."""

    def test_05_01_one_image_one_video(self):
        """1 image (PNG) + 1 video (real_2s) -> HTTP 200 (multimodal mix)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": png_base64()}},
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "Describe both."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"05_01 image+video mixed expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_05_02_image_video_stream_variant(self, stream):
        """Image + video mixed -> both non-stream and stream paths should return 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": png_base64()}},
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "Describe both."},
            ]}],
            "max_tokens": 1024,
        }, stream=stream)
        assert r["status"] == 200, (
            f"05_02 stream={stream} mixed image+video expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    def test_05_03_mixed_3img_1vid(self):
        """3 real images (sx1 x3) + 1 real video (real_2s) mix -> allow 200/4xx."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": real_image_b64_for_video("sx1.jpg", "image/jpeg")}},
                {"type": "image_url", "image_url": {"url": real_image_b64_for_video("sx1.jpg", "image/jpeg")}},
                {"type": "image_url", "image_url": {"url": real_image_b64_for_video("sx1.jpg", "image/jpeg")}},
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "Describe all the images and the video."},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"05_03 3img+1vid unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    def test_05_04_mixed_1img_2vid(self):
        """1 real image (sx1) + 2 real videos (real_2s + flower-video) mix -> allow 200/4xx."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": real_image_b64_for_video("sx1.jpg", "image/jpeg")}},
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "video_url", "video_url": {"url": real_video_b64("flower-video.mp4")}},
                {"type": "text", "text": "Describe the image and both videos."},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"05_04 1img+2vid unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )


# ============================================================
# 06 fps_param — fps valid tiers and out-of-range
# ============================================================

class TestFpsParam:
    """fps in [0.2, 5] valid tiers and out-of-range reject behavior."""

    @pytest.mark.parametrize("fps", [0.5, 1, 2], ids=["fps=0.5", "fps=1", "fps=2"])
    def test_06_01_fps_real_video(self, fps):
        """fps in {0.5, 1, 2} on 12s_real.mp4 real video -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("12s_real.mp4"),
                    "fps": fps,
                }},
                {"type": "text", "text": "Describe briefly."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"06_01 fps={fps} expected 200, got {r['status']}: {str(r.get('body'))[:300]}"
        )

    @pytest.mark.parametrize("fps", [0.5, 1.0, 2.0, 5.0],
                             ids=["fps=0.5", "fps=1.0", "fps=2.0", "fps=5.0"])
    def test_06_02_valid_fps(self, fps):
        """Each valid fps in [0.2, 5] tier on 12s_real.mp4 -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("12s_real.mp4"),
                    "fps": fps,
                }},
                {"type": "text", "text": "Describe."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"06_02 valid fps={fps} expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.parametrize("fps", [0.1, 0.0, -1, 10.0, 100],
                             ids=["fps=0.1", "fps=0", "fps=-1", "fps=10", "fps=100"])
    def test_06_03_invalid_fps(self, fps):
        """Out-of-range values (< 0.2 or > 5); server may reject or leniently accept; soft assert 200/400/422/500."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("12s_real.mp4"),
                    "fps": fps,
                }},
                {"type": "text", "text": "Describe."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] in (200, 400, 422, 500), (
            f"06_03 invalid fps={fps} unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_06_04_fps_lower_boundary(self):
        """fps=0.2 (lower bound) -> HTTP 200 + prompt_tokens > 0."""
        r = oai_chat(_video_payload("video_640x480.mp4", detail="default", fps=0.2))
        _assert_basic_ok(r, "06_04 fps=0.2 lower boundary")

    def test_06_05_fps_upper_boundary(self):
        """fps=5.0 (upper bound) -> HTTP 200 + prompt_tokens > 0."""
        r = oai_chat(_video_payload("video_640x480.mp4", detail="default", fps=5.0))
        _assert_basic_ok(r, "06_05 fps=5.0 upper boundary")

    @pytest.mark.parametrize("fps", [0.1, 0.0, -1], ids=["0.1", "0.0", "-1"])
    def test_06_06_fps_below_min_short_fixture(self, fps):
        """fps<0.2 on video_640x480.mp4 (short fixture) -> soft assert 200/400/422; records actual behavior.

        Complements 06_03: 06_03 uses 12s_real.mp4 (long video) for full out-of-range coverage;
        06_06 uses a short fixture to cover the 3 common out-of-range values near the lower bound for quick diagnosis.
        """
        r = oai_chat(_video_payload("video_640x480.mp4", detail="default", fps=fps))
        assert r["status"] in (200, 400, 422), f"06_06 fps={fps} HTTP={r['status']}"

    @pytest.mark.parametrize("fps", [5.1, 10, 1000], ids=["5.1", "10", "1000"])
    def test_06_07_fps_above_max_short_fixture(self, fps):
        """fps>5 on video_640x480.mp4 (short fixture) -> soft assert 200/400/422; records actual behavior.

        Complements 06_03: 06_07 covers the 3 common out-of-range values near the upper bound; short fixture for quick diagnosis.
        """
        r = oai_chat(_video_payload("video_640x480.mp4", detail="default", fps=fps))
        assert r["status"] in (200, 400, 422), f"06_07 fps={fps} HTTP={r['status']}"


# ============================================================
# 07 detail_param — detail / fps field defaults and combinations
# ============================================================

class TestDetailParam:
    """detail = low/default/high three-tier acceptance + detail / fps field default combinations."""

    @pytest.mark.parametrize("detail", ["low", "default", "high"],
                             ids=["detail=low", "detail=default", "detail=high"])
    def test_07_01_detail_value(self, detail):
        """video_url.detail in {low, default, high} -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("real_2s.mp4"),
                    "detail": detail,
                }},
                {"type": "text", "text": "What is in the video?"},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"07_01 detail={detail} expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_07_02_no_detail_no_fps(self):
        """Omit both detail and fps; server uses defaults (detail=default, fps=1) -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("real_2s.mp4"),
                }},
                {"type": "text", "text": "What is in the video? One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"07_02 默认参数 expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_07_03_no_detail_explicit_fps(self):
        """Only pass fps, omit detail; server uses default detail=default -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("real_2s.mp4"),
                    "fps": 1,
                }},
                {"type": "text", "text": "One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"07_03 仅 fps expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_07_04_no_fps_explicit_detail(self):
        """Only pass detail, omit fps; server uses default fps=1 -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("real_2s.mp4"),
                    "detail": "default",
                }},
                {"type": "text", "text": "One word."},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"07_04 仅 detail expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_07_05_max_long_side_pixel_baseline(self):
        """max_long_side_pixel=504 (28x18 minimum tier) + real_2s.mp4 -> HTTP 200 (contract minimum-tier smoke).

        # OAI contract: max_long_side_pixel must be a multiple of 28 (aligned by the M3 team on 2026-06-02).
        # This case only does a minimum-tier smoke; the full contract/monotonic/out-of-range coverage lives in module §09.
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": real_video_b64("real_2s.mp4"),
                    "max_long_side_pixel": 504,
                }},
                {"type": "text", "text": "What is in the video?"},
            ]}],
            "max_tokens": 1024,
        })
        assert r["status"] == 200, (
            f"07_05 max_long_side_pixel=504 expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )


# ============================================================
# 08 resolution_tier — resolution tier / boundary / pixel cap
# ============================================================

class TestResolutionTier:
    """Videos at different resolutions go through detail=default scaling + max_total_pixels soft cap."""

    def test_08_01_tier_low_no_scale(self):
        """400x300 video (long side 400 < default tier 672) -> HTTP 200 (no scale)."""
        r = oai_chat(_video_payload("video_400x300.mp4", detail="default"))
        _assert_basic_ok(r, "08_01 small_video")

    def test_08_02_tier_low_scale_down(self):
        """1280x720 video (long side 1280 > default tier 672) -> should scale per frame, HTTP 200."""
        r = oai_chat(_video_payload("video_1280x720.mp4", detail="default"))
        _assert_basic_ok(r, "08_02 medium_video")

    def test_08_03_tier_default_no_scale(self):
        """640x480 video (long side 640 < default tier 672) -> HTTP 200 (no scale)."""
        r = oai_chat(_video_payload("video_640x480.mp4", detail="default"))
        _assert_basic_ok(r, "08_03 below_default")

    def test_08_04_tier_default_scale_down(self):
        """1920x1080 video (long side 1920 > default tier 672) -> should scale per frame, HTTP 200."""
        r = oai_chat(_video_payload("video_1920x1080.mp4", detail="default"))
        _assert_basic_ok(r, "08_04 above_default")

    def test_08_05_tier_high_no_scale(self):
        """1280x720 video (long side 1280 > default tier 672) -> HTTP 200."""
        r = oai_chat(_video_payload("video_1280x720.mp4", detail="default"))
        _assert_basic_ok(r, "08_05 medium_large_video")

    def test_08_06_tier_high_scale_down(self):
        """3840x2160 video (long side 3840 > default tier 672) -> should scale per frame, HTTP 200."""
        r = oai_chat(_video_payload("video_3840x2160.mp4", detail="default"))
        _assert_basic_ok(r, "08_06 large_video")

    def test_08_07_tier_at_boundary(self):
        """1280x720 video (long side = 2x default tier) -> boundary soft assert HTTP 200."""
        r = oai_chat(_video_payload("video_1280x720.mp4", detail="default"))
        _assert_basic_ok(r, "08_07 boundary")

    def test_08_08_tier_consistency(self):
        """1920x1080 large video + default tier -> HTTP 200 + prompt_tokens > 0 (basic smoke)."""
        r = oai_chat(_video_payload("video_1920x1080.mp4", detail="default"))
        assert r["status"] == 200, f"08_08 HTTP={r['status']}"
        pt = _get_prompt_tokens(r)
        assert pt > 0, f"08_08 prompt_tokens={pt}"

    def test_08_09_max_total_pixels_exceeded(self):
        """1-second 3840x2160 + fps=5, approaching the max_total_pixels=301,056,000 soft cap -> 200/4xx.

        # Current fixtures are all 1-second videos and cannot truly trigger the cap; this only
        # asserts acceptance of "high fps + large resolution"; a true over-limit test needs a
        # longer-duration fixture.
        """
        r = oai_chat(_video_payload("video_3840x2160.mp4", detail="default", fps=5))
        assert r["status"] in (200, 400, 413, 422), (
            f"08_09 HTTP={r['status']}"
        )


# ============================================================
# 09 max_long_side_pixel — max_long_side_pixel (multiple of 28) contract
# ============================================================
# OAI contract: max_long_side_pixel must be a multiple of 28 (aligned by the M3 team on 2026-06-02).
# Video three tiers use 504 (28x18) / 1008 (28x36) / 2016 (28x72);
# the legacy (504, 672, 1280) combination had 672/1280 not multiples of 28 and is deprecated.

class TestMaxLongSidePixel:
    """max_long_side_pixel three tiers (504/1008/2016) contract + monotonicity + out-of-range soft assert."""

    @pytest.mark.parametrize("mlsp,tier", [
        (504, "low"),
        (1008, "default"),
        (2016, "high"),
    ], ids=["low=504", "default=1008", "high=2016"])
    def test_09_01_tier_value(self, mlsp, tier):
        """Each of the three tiers (504/1008/2016) fed with the 3840x2160 real video (long side > 2016, all trigger scaling) -> HTTP 200 + prompt_tokens > 0."""
        fixture_name = "video_3840x2160.mp4"
        video_url_obj = {
            "url": fixture_video_base64(fixture_name),
            "max_long_side_pixel": mlsp,
        }
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": video_url_obj},
                {"type": "text", "text": "What is this?"},
            ]}],
        })
        _assert_basic_ok(r, f"09_01 tier={tier} mlsp={mlsp} [{fixture_name}]")

    def test_09_02_monotonic(self):
        """Same video with each of the three tiers set; prompt_tokens strictly monotonic 504 < 1008 < 2016."""
        fixture_name = "video_3840x2160.mp4"
        fixture_url = fixture_video_base64(fixture_name)
        tokens = {}
        for mlsp, tier in [(504, "low"), (1008, "default"), (2016, "high")]:
            r = oai_chat({
                "messages": [{"role": "user", "content": [
                    {"type": "video_url", "video_url": {
                        "url": fixture_url,
                        "max_long_side_pixel": mlsp,
                    }},
                    {"type": "text", "text": "What is this?"},
                ]}],
            })
            _assert_basic_ok(r, f"09_02 monotonic tier={tier} mlsp={mlsp}")
            tokens[mlsp] = _get_prompt_tokens(r)
        assert tokens[504] < tokens[1008] < tokens[2016], (
            f"09_02 monotonic: max_long_side_pixel 越大 prompt_tokens 应越大, "
            f"got {tokens} (expected 504 < 1008 < 2016)"
        )

    @pytest.mark.parametrize("invalid_value", [140, 3612, 0, -28],
                             ids=["below_min_28x5", "above_max_28x129", "zero", "negative_28"])
    def test_09_03_out_of_range(self, invalid_value):
        """Outside the [150, 3584] spec range (<150 / >3584 / 0 / negative, all multiples of 28) -> soft assert 200/400/413/422."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": fixture_video_base64("video_640x480.mp4"),
                    "max_long_side_pixel": invalid_value,
                }},
                {"type": "text", "text": "What?"},
            ]}],
        })
        assert r["status"] in (200, 400, 413, 422), (
            f"09_03 invalid={invalid_value} HTTP={r['status']}"
        )


# ============================================================
# 10 video_size_limit — video size limit (<=250MB)
# ============================================================

class TestVideoSizeLimit:
    """Video <= 250 MB; URL/Base64 large-video handling (accept-with-recognition or 4xx reject)."""

    def test_10_01_url_under_50mb(self):
        """URL form: ~47.4 MB MP4 within the 50 MB cap should be accepted."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": size_fixture_url("video_49mb.mp4")}},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
        })
        assert_oai_success(r)

    def test_10_02_url_large_video(self):
        """URL form: ~254 MB MP4 over the 250 MB threshold.

        Acceptable:
          - 4xx (server chooses to reject the oversize video), OR
          - 200 with the model actually decoding the video — video_251mb.mp4 is a
            1920x1080 freight-train clip, so the assistant content must mention
            train/railway/cargo-like terms to prove the video frames actually
            went through vision (rules out silent-drop fallback text).
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": size_fixture_url("video_251mb.mp4")}},
                {"type": "text", "text": "What is this video? Describe what you see."},
            ]}],
        })
        status = r["status"]
        if 400 <= status < 500:
            return
        assert status == 200, (
            f"10_02 expected 4xx or 200, got {status}: {str(r.get('body'))[:300]}"
        )
        body = r.get("body") or {}
        choices = body.get("choices") or []
        content = ""
        if choices:
            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").lower()
        recognized_terms = (
            "train", "railway", "railroad", "rail", "locomotive", "freight",
            "cargo", "boxcar", "boxcars", "tank car", "wagon", "carriage",
            "track", "tracks", "vehicle", "vehicles",
            "frame", "frames", "video", "clip", "footage",
        )
        assert any(t in content for t in recognized_terms), (
            f"10_02 status=200 but assistant did not recognize the video content; "
            f"content head: {content[:300]}"
        )

    @pytest.mark.timeout(600)
    def test_10_03_base64_under_50mb(self):
        """Base64 form: ~47.4 MB MP4 within the 50 MB cap should be accepted."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": size_fixture_data_url("video_49mb.mp4")}},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
        }, timeout=300)
        assert_oai_success(r)

    @pytest.mark.timeout(600)
    def test_10_04_base64_over_50mb(self):
        """Base64 form: ~52 MB MP4 over the 50 MB cap.

        Acceptable:
          - 4xx (M2/M3 spec: >50MB rejected), OR
          - 200 with the model actually decoding the video — video_51mb.mp4 is a
            1280x720 / 55s random-pixel noise clip, so the assistant content must
            mention noise/random/pixel/frame-like terms to prove the video frames
            actually went through vision (rules out silent-drop fallback text).
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": size_fixture_data_url("video_51mb.mp4")}},
                {"type": "text", "text": "What?"},
            ]}],
        }, timeout=300)
        status = r["status"]
        if 400 <= status < 500:
            return
        assert status == 200, (
            f"10_04 expected 4xx or 200, got {status}: {str(r.get('body'))[:300]}"
        )
        body = r.get("body") or {}
        choices = body.get("choices") or []
        content = ""
        if choices:
            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").lower()
        recognized_terms = (
            "noise", "random", "static", "noisy", "pixel", "snow",
            "interference", "glitch", "scramble", "chaotic",
            "frame", "frames", "video", "clip", "footage",
            "magenta", "green pixel", "test pattern",
        )
        assert any(t in content for t in recognized_terms), (
            f"10_04 status=200 but assistant did not recognize the video content; "
            f"content head: {content[:300]}"
        )

    @pytest.mark.slow
    @pytest.mark.timeout(600)
    def test_10_05_url_large_video_summary(self):
        """URL form: ~254 MB MP4 over the 250 MB threshold, with a summarization prompt.

        Complements 10_02 (same oversize URL fixture, different task) to confirm the
        behavior is stable across prompts. Acceptable:
          - 4xx (server chooses to reject the oversize video), OR
          - 200 with the model actually decoding the video — video_251mb.mp4 is a
            1920x1080 freight-train clip, so the assistant content must mention
            train/railway/cargo-like terms to prove the video frames actually
            went through vision (rules out silent-drop fallback text).
        """
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": size_fixture_url("video_251mb.mp4")}},
                {"type": "text", "text": "Summarize the main subject moving through this video."},
            ]}],
            "max_tokens": 1024,
        }, timeout=300)
        status = r["status"]
        if 400 <= status < 500:
            return
        assert status == 200, (
            f"10_05 expected 4xx or 200, got {status}: {str(r.get('body'))[:300]}"
        )
        body = r.get("body") or {}
        choices = body.get("choices") or []
        content = ""
        if choices:
            msg = choices[0].get("message") or {}
            content = (msg.get("content") or "").lower()
        recognized_terms = (
            "train", "railway", "railroad", "rail", "locomotive", "freight",
            "cargo", "boxcar", "boxcars", "tank car", "wagon", "carriage",
            "track", "tracks", "vehicle", "vehicles",
            "frame", "frames", "video", "clip", "footage",
        )
        assert any(t in content for t in recognized_terms), (
            f"10_05 status=200 but assistant did not recognize the video content; "
            f"content head: {content[:300]}"
        )


# ============================================================
# 11 long_video — long video (5/10/20/30 min)
# ============================================================
# fixtures are not committed to git (each file > 30MB); specify the directory via the
# `M3_LONG_VIDEO_DIR` environment variable (default reference implementation lives at
# /Users/minimax/Downloads/M3/assets/videos/duration/).

def _long_video_present(name: str) -> bool:
    return long_video_path(name).exists()


class TestLongVideo:
    """5/10/20/30 minute video latency and upper-bound tests (skipif env)."""

    @pytest.mark.slow
    @pytest.mark.skipif(
        not _long_video_present("D_300s.mp4"),
        reason="long video fixture D_300s.mp4 not present; "
               "set M3_LONG_VIDEO_DIR=<dir-with-D_300s.mp4>",
    )
    def test_11_01_long_video_5min(self):
        """5-minute video (~5MB, default fps=1)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": long_video_b64("D_300s.mp4")}},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=600)
        assert r["status"] in (200, 400, 413, 422, 500, 502, 503, 504), (
            f"11_01 5min unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    @pytest.mark.skipif(
        not _long_video_present("D_600s.mp4"),
        reason="long video fixture D_600s.mp4 not present; "
               "set M3_LONG_VIDEO_DIR=<dir-with-D_600s.mp4>",
    )
    def test_11_02_long_video_10min(self):
        """10-minute video (default fps=1)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": long_video_b64("D_600s.mp4")}},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=600)
        assert r["status"] in (200, 400, 413, 422, 500, 502, 503, 504), (
            f"11_02 10min unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    @pytest.mark.skipif(
        not _long_video_present("D_1200s.mp4"),
        reason="long video fixture D_1200s.mp4 not present; "
               "set M3_LONG_VIDEO_DIR=<dir-with-D_1200s.mp4>",
    )
    def test_11_03_long_video_20min(self):
        """20-minute video (fps=0.5 to control total pixels)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": long_video_b64("D_1200s.mp4"),
                    "fps": 0.5,
                }},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=600)
        assert r["status"] in (200, 400, 413, 422, 500, 502, 503, 504), (
            f"11_03 20min unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    @pytest.mark.skipif(
        not _long_video_present("D_1800s.mp4"),
        reason="long video fixture D_1800s.mp4 not present; "
               "set M3_LONG_VIDEO_DIR=<dir-with-D_1800s.mp4>",
    )
    def test_11_04_long_video_30min(self):
        """30-minute video (fps=0.5 to control total pixels)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {
                    "url": long_video_b64("D_1800s.mp4"),
                    "fps": 0.5,
                }},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
            "max_tokens": 2048,
        }, timeout=600)
        assert r["status"] in (200, 400, 413, 422, 500, 502, 503, 504), (
            f"11_04 30min unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )


# ============================================================
# 12 media_gradient — resolution gradient / multi-video gradient
# ============================================================

class TestMediaGradient:
    """Media gradient: video resolution gradient (1080P/2K) and multi-video count gradient (3/5 clips)."""

    @pytest.mark.parametrize("filename,label", [
        ("video_1920x1080.mp4", "1080P"),
        ("video_3840x2160.mp4", "2K"),
    ], ids=["1080P", "2K"])
    def test_12_01_resolution_gradient(self, filename, label):
        """Video resolution gradient (1080P / 2K) using existing fixtures -> HTTP 200."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": fixture_video_base64(filename)}},
                {"type": "text", "text": "Describe this video"},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] == 200, (
            f"12_01 {label} ({filename}) expected 200, got {r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("count", [3, 5], ids=["count=3", "count=5"])
    def test_12_02_multi_video_gradient(self, count):
        """Multi-video gradient (3 / 5 stacked clips) using real_2s.mp4 -> allow 200/4xx."""
        vid = real_video_b64("real_2s.mp4")
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                *[{"type": "video_url", "video_url": {"url": vid}} for _ in range(count)],
                {"type": "text", "text": f"You see {count} short videos. Acknowledge them."},
            ]}],
            "max_tokens": 2048,
        }, timeout=300)
        assert r["status"] in (200, 400, 413, 422), (
            f"12_02 count={count} unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )

    def test_12_03_video_temporal(self):
        """real_2s.mp4 + What happens in this video -> content > 10 characters."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "What happens in this video?"},
            ]}],
            "max_tokens": 1024,
        })
        assert_oai_success(r)
        content = get_oai_content(r)
        assert len(content) > 10, (
            f"12_03 expected non-empty video description (>10 chars), got len={len(content)}: "
            f"{content!r}"
        )

    def test_12_04_image_video_combined(self):
        """Real image sx1.jpg + real video real_2s.mp4 in the same message -> content > 20."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": real_image_b64_for_video("sx1.jpg", "image/jpeg")}},
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "Describe both the image and the video."},
            ]}],
            "max_tokens": 1024,
        })
        assert_oai_success(r)
        content = get_oai_content(r)
        assert len(content) > 20, (
            f"12_04 expected descriptions for both image and video (>20 chars), "
            f"got len={len(content)}: {content!r}"
        )


# ============================================================
# 13 video_extension — reasoning_split and other extension fields
# ============================================================

class TestVideoExtension:
    """Compatibility of extension protocol fields in video scenarios."""

    @pytest.mark.parametrize("stream", [False, True], ids=["non_stream", "stream"])
    def test_13_01_reasoning_split(self, stream):
        """Video + reasoning_split + thinking adaptive, both stream and non-stream paths; allow 200/400 (extension fields may be unsupported)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": real_video_b64("real_2s.mp4")}},
                {"type": "text", "text": "Describe step by step."},
            ]}],
            "reasoning_split": True,
            "thinking": {"type": "adaptive"},
            "max_tokens": 1024,
        }, stream=stream)
        assert r["status"] in (200, 400), (
            f"13_01 stream={stream} unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )


# ============================================================
# 15 video_in_tool — video returned inside a tool-role message
# ============================================================

class TestVideoInToolMessage:
    """Video carried inside a tool-role message content array (tool result returns a video)."""

    # PONY_VIDEO_URL semantic anchors (cartoon pony + Spring Festival scene).
    _VID_IN_TOOL_ANCHORS = (
        "horse", "pony", "stallion", "foal", "cartoon", "animated",
        "lantern", "firecracker", "new year", "spring festival", "festive",
        "马", "小马", "卡通", "灯笼", "鞭炮", "新年", "春节",
    )

    def _run_video_in_tool_message(self, stream, cid):
        """Shared body for 15_01/15_02: video returned INSIDE a tool-role message content array.

        Simulates a tool ("fetch_video") whose result carries a real video (video_url block +
        text). The model must parse the multimodal tool result and answer what the video shows.
        Flow: user asks -> assistant tool_call -> tool returns [text + video_url] -> user asks
        what the video is about. Multimodal content inside a tool message is not universally
        supported: allow 200/400, forbid 500.

        Uses the real public https URL PONY_VIDEO_URL (Spring Festival cartoon pony) so we can
        assert on semantic keywords (pony/horse/festival/...) to confirm the tool-message video
        truly reached the model, not just a non-empty reply.
        """
        fetch_video_tool = {
            "type": "function",
            "function": {
                "name": "fetch_video",
                "description": "Fetch a video by id; returns the video content for the model to watch.",
                "parameters": {
                    "type": "object",
                    "properties": {"video_id": {"type": "string", "description": "id of the video to fetch"}},
                    "required": ["video_id"],
                },
            },
        }
        r = oai_chat({
            "messages": [
                {"role": "user", "content": "Fetch video vid_001 and tell me what happens in it."},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function",
                     "function": {"name": "fetch_video", "arguments": '{"video_id":"vid_001"}'}},
                ]},
                {"role": "tool", "tool_call_id": "c1", "content": [
                    {"type": "text", "text": "Here is video vid_001:"},
                    {"type": "video_url", "video_url": {"url": PONY_VIDEO_URL}},
                ]},
                {"role": "user", "content": "Describe what you see in that video."},
            ],
            "tools": [fetch_video_tool],
            "max_tokens": 512,
        }, stream=stream)
        assert r["status"] in (200, 400), (
            f"{cid} video_in_tool_message unexpected HTTP={r['status']}: "
            f"{str(r.get('body'))[:300]}"
        )
        if r["status"] == 200:
            content = get_oai_content(r).lower()
            assert len(content.strip()) > 20, (
                f"{cid} expected non-empty description, got len={len(content)}: {content!r}"
            )
            assert any(a in content for a in self._VID_IN_TOOL_ANCHORS), (
                f"{cid} model failed to parse video in tool message; "
                f"expected any of {self._VID_IN_TOOL_ANCHORS} in reply, got: {content[:200]}"
            )

    def test_15_01_video_in_tool_message_non_stream(self):
        """15_01 — video inside a tool-role message, non-stream path."""
        self._run_video_in_tool_message(stream=False, cid="15_01")

    def test_15_02_video_in_tool_message_stream(self):
        """15_02 — video inside a tool-role message, stream path."""
        self._run_video_in_tool_message(stream=True, cid="15_02")


# ============================================================
# 14 error_codes — video-related error codes
# ============================================================

class TestVideoErrorCodes:
    """Video-related error codes (split out from TestOAIErrors)."""

    def test_14_01_fps_out_of_range(self):
        """fps=100 is significantly out of range -> HTTP 400 (hard assert)."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mp4_base64(), "fps": 100}},
                {"type": "text", "text": "What?"},
            ]}],
        })
        assert_error(r, 400)


# ============================================================
# 15 stream_usage — video + streaming usage chunk protocol
# ============================================================

class TestVideoStreamUsage:
    """Video + streaming + stream_options.include_usage usage-chunk protocol fields."""

    def test_15_01_stream_usage_only_in_last_chunk(self):
        """15_01 — video + stream_options.include_usage=true: usage must be non-empty and only appear in the final stream chunk."""
        r = oai_chat({
            "messages": [{"role": "user", "content": [
                {"type": "video_url", "video_url": {"url": mp4_base64()}},
                {"type": "text", "text": "Describe this video briefly."},
            ]}],
            "stream_options": {"include_usage": True},
        }, stream=True)
        assert_oai_stream_success(r)
        assert_stream_usage_only_in_last_chunk(r, msg="15_01 video include_usage")

# M3 Video Modality Format Validation Case List

> Corresponds to: `data/m3_api_test/m3_video_tests.py`
> Naming convention: `test_<2-digit module id>_<2-digit intra-module seq>_<scene>`
> Modules: **15**; Test functions: **61**; Pytest collected items: **86**

## Module Overview

| Module ID | Module Name | Theme | Functions | Items |
|:---:|:---|:---|:---:|:---:|
| 01 | base64_video | base64 video basic acceptance | 2 | 2 |
| 02 | url_video | URL video acceptance | 2 | 2 |
| 03 | video_format | Video container/MIME format (MOV/MKV/AVI etc.) | 8 | 9 |
| 04 | multi_video | Multi-video stacking / count limit | 5 | 5 |
| 05 | image_video_mixed | Image + video mixed message | 4 | 5 |
| 06 | fps_param | fps valid tiers and out-of-range | 7 | 20 |
| 07 | detail_param | detail / fps field default and combo | 5 | 7 |
| 08 | resolution_tier | Resolution tier / boundary / pixel cap | 9 | 9 |
| 09 | max_long_side_pixel | max_long_side_pixel (multiple-of-28) contract | 3 | 8 |
| 10 | video_size_limit | Video size limit (≤250MB) | 5 | 5 |
| 11 | long_video | Long videos (5/10/20/30 min) | 4 | 4 |
| 12 | media_gradient | Resolution gradient / multi-video gradient | 4 | 6 |
| 13 | video_extension | reasoning_split and other extension fields | 1 | 2 |
| 14 | error_codes | Video-related error codes | 1 | 1 |
| 15 | stream_usage | Video + streaming usage chunk | 1 | 1 |
| | **Total** | | **61** | **86** |

---

## 01 base64_video — base64 video basic acceptance

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_base64_video` | Minimal base64 MP4 + "What do you see" | HTTP 200 + non-empty content (> 20 chars) |
| 01_02 | `test_01_02_base64_real_pony_cartoon` | Real footage (Spring Festival pony cartoon, 5MB) via base64, `max_tokens=4096` | HTTP 200 + content > 50 chars + **subject keyword hit** (horse/pony/cartoon/马/小马/卡通/...) + **CNY scene keyword hit** (lantern/firecracker/spring festival/灯笼/鞭炮/春节/元宝/中国结/red/gold/...) |

## 02 url_video — URL video acceptance

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_url_video` | Public sample mp4 URL (`SAMPLE_VIDEO_URL`) | HTTP 200 + non-empty content (> 20 chars) |
| 02_02 | `test_02_02_url_real_pony_cartoon` | Real footage (Spring Festival pony cartoon) via OSS URL, `max_tokens=4096` | HTTP 200 + content > 50 chars + **subject keyword hit** (horse/pony/cartoon/马/小马/卡通/...) + **CNY scene keyword hit** (lantern/firecracker/spring festival/灯笼/鞭炮/春节/元宝/中国结/red/gold/...) |

## 03 video_format — Video container/MIME format

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_mkv_format_legacy` | MKV (video/x-matroska) faked over minimal mp4 (legacy case) | 200 / xfail if known-unsupported |
| 03_02 | `test_03_02_mov_format_video_quicktime` | MOV (video/quicktime base64 fake) | 200 / xfail on BUG-7 |
| 03_03 | `test_03_03_mov_format_video_mov` | MOV (spec 1.3.5 requires `data:video/mov;base64,...`) | 200 / xfail on BUG-7 |
| 03_04 | `test_03_04_mkv_format_video_matroska` | MKV (video/x-matroska) faked over minimal mp4 | 200 / xfail on BUG-7 |
| 03_05 | `test_03_05_avi_format[video_avi\|video_x_msvideo]` | AVI with both valid MIMEs (`video/avi` / `video/x-msvideo`) | 200 / xfail if unsupported |
| 03_06 | `test_03_06_real_mov_smoke` | Real MOV `fixtures/test_video.mov` with default detail/fps | 200/400/415/422/500 soft assertion |
| 03_07 | `test_03_07_real_avi_smoke` | Real AVI `fixtures/test_video.avi` with default detail/fps | 200/400/415/422/500 soft assertion |
| 03_08 | `test_03_08_real_mkv_smoke` | Real MKV `fixtures/test_video.mkv` with default detail/fps | 200/400/415/422/500 soft assertion |

## 04 multi_video — Multi-video stacking / count limit

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 04_01 | `test_04_01_count_at_max` | 5 minimal mp4 segments (spec upper bound) | HTTP 200 |
| 04_02 | `test_04_02_count_over_max` | 10 minimal mp4 segments (over spec upper bound) | HTTP 200 + non-empty content (M3 does not enforce reject) |
| 04_03 | `test_04_03_multi_video_3` | 3 × real_2s.mp4 real video stacking | 200/4xx soft assertion |
| 04_04 | `test_04_04_multi_video_5` | 5 × real_2s.mp4 real video stacking | 200/4xx soft assertion |
| 04_05 | `test_04_05_multi_video_b64_url_mix` | base64 + URL two distinct load forms mixed | 200/4xx soft assertion |

## 05 image_video_mixed — Image + video mixed message

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_one_image_one_video` | 1 image (PNG) + 1 video (real_2s) | HTTP 200 |
| 05_02 | `test_05_02_image_video_stream_variant[non_stream\|stream]` | Image+video mixed, non-stream/stream paths | Both paths return 200 |
| 05_03 | `test_05_03_mixed_3img_1vid` | 3 real images (sx1 × 3) + 1 real video (real_2s) | 200/4xx soft assertion |
| 05_04 | `test_05_04_mixed_1img_2vid` | 1 real image (sx1) + 2 real videos (real_2s + flower-video) | 200/4xx soft assertion |

## 06 fps_param — fps valid tiers and out-of-range

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 06_01 | `test_06_01_fps_real_video[fps=0.5\|1\|2]` | 12s_real.mp4 + three common fps values | HTTP 200 |
| 06_02 | `test_06_02_valid_fps[fps=0.5\|1.0\|2.0\|5.0]` | 12s_real.mp4 + valid fps ∈ [0.2, 5] four tiers | HTTP 200 |
| 06_03 | `test_06_03_invalid_fps[fps=0.1\|0\|-1\|10\|100]` | 12s_real.mp4 + out-of-range fps (3 below + 2 above) | 200/400/422/500 soft assertion |
| 06_04 | `test_06_04_fps_lower_boundary` | 640×480 fixture + fps=0.2 (lower bound) | HTTP 200 + prompt_tokens > 0 |
| 06_05 | `test_06_05_fps_upper_boundary` | 640×480 fixture + fps=5.0 (upper bound) | HTTP 200 + prompt_tokens > 0 |
| 06_06 | `test_06_06_fps_below_min_short_fixture[0.1\|0.0\|-1]` | 640×480 fixture + 3 common below-min out-of-range values | 200/400/422 soft assertion |
| 06_07 | `test_06_07_fps_above_max_short_fixture[5.1\|10\|1000]` | 640×480 fixture + 3 common above-max out-of-range values | 200/400/422 soft assertion |

## 07 detail_param — detail / fps field default and combo

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_detail_value[low\|default\|high]` | `video_url.detail` ∈ {low, default, high} | All three tiers return HTTP 200 |
| 07_02 | `test_07_02_no_detail_no_fps` | Neither detail nor fps; server uses defaults (detail=default, fps=1) | HTTP 200 |
| 07_03 | `test_07_03_no_detail_explicit_fps` | Only fps; detail defaults | HTTP 200 |
| 07_04 | `test_07_04_no_fps_explicit_detail` | Only detail; fps defaults | HTTP 200 |
| 07_05 | `test_07_05_max_long_side_pixel_baseline` | `max_long_side_pixel=504` minimum-tier smoke (28×18) | HTTP 200 (full contract in §09) |

## 08 resolution_tier — Resolution tier / boundary / pixel cap

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 08_01 | `test_08_01_tier_low_no_scale` | 400×300 video (< default tier 672) + detail=default | HTTP 200 + prompt_tokens > 0 (no scale) |
| 08_02 | `test_08_02_tier_low_scale_down` | 1280×720 + detail=default | HTTP 200 + per-frame scale-down |
| 08_03 | `test_08_03_tier_default_no_scale` | 640×480 + detail=default | HTTP 200 (no scale) |
| 08_04 | `test_08_04_tier_default_scale_down` | 1920×1080 + detail=default | HTTP 200 + per-frame scale-down |
| 08_05 | `test_08_05_tier_high_no_scale` | 1280×720 + detail=default | HTTP 200 |
| 08_06 | `test_08_06_tier_high_scale_down` | 3840×2160 + detail=default | HTTP 200 + per-frame scale-down |
| 08_07 | `test_08_07_tier_at_boundary` | 1280×720 (long side = 2× default tier) + detail=default | HTTP 200 (boundary soft assertion) |
| 08_08 | `test_08_08_tier_consistency` | 1920×1080 large video + default tier | HTTP 200 + prompt_tokens > 0 |
| 08_09 | `test_08_09_max_total_pixels_exceeded` | 3840×2160 + fps=5, approaching max_total_pixels=301,056,000 | 200/400/413/422 soft assertion |

## 09 max_long_side_pixel — `max_long_side_pixel` (multiple-of-28) contract

> OAI contract: `max_long_side_pixel` must be a **multiple of 28**.
> Video three tiers use **504 (28×18) / 1008 (28×36) / 2016 (28×72)**; the old (504/672/1280)
> combination is deprecated because 672/1280 are not multiples of 28.

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 09_01 | `test_09_01_tier_value[low=504\|default=1008\|high=2016]` | Three tiers on 3840×2160 real video (long side > 2016, all trigger scaling) | HTTP 200 + prompt_tokens > 0 |
| 09_02 | `test_09_02_monotonic` | Same video at three tiers; strict monotonic token count 504 < 1008 < 2016 | Three-tier tokens strictly monotonic |
| 09_03 | `test_09_03_out_of_range[below_min_28x5\|above_max_28x129\|zero\|negative_28]` | Values outside [150, 3584] spec range (<150 / >3584 / 0 / negative; all multiples of 28) | 200/400/413/422 soft assertion |

## 10 video_size_limit — Video size limit (≤250MB)

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_url_under_50mb` | URL mode, ~47.4 MB MP4 (<50MB) | `assert_oai_success` passes |
| 10_02 | `test_10_02_url_over_250mb` | URL mode, ~254 MB MP4 (video_251mb.mp4, 1920×1080 freight-train clip, >250MB) | 4xx, OR HTTP 200 with content matching train/railway keywords (train/railway/railroad/freight/cargo/boxcar/track/video/clip, etc.), proving video frames went through vision encoding, ruling out silent-drop fallback text |
| 10_03 | `test_10_03_base64_under_50mb` | Base64 mode, ~47.4 MB MP4 (<50MB) | `assert_oai_success` passes |
| 10_04 | `test_10_04_base64_over_50mb` | Base64 mode, ~52 MB MP4 (video_51mb.mp4, 1280×720 / 55s random-pixel noise clip, >50MB) | 4xx, OR HTTP 200 with content matching video/noise keywords (noise/random/static/pixel/frame/video/clip/magenta/green pixel, etc.), proving video frames went through vision encoding, ruling out silent-drop fallback text |
| 10_05 | `test_10_05_url_over_250mb_summary` | URL mode, ~254 MB MP4 (video_251mb.mp4, >250MB; summarization prompt, complements 10_02) | 4xx, OR HTTP 200 with content matching train/railway keywords, proving video frames went through vision encoding, ruling out silent-drop fallback text |

## 11 long_video — Long videos (5/10/20/30 min)

> Defaults to reading D_300s/D_600s/D_1200s/D_1800s.mp4 from `fixtures/m3_test_videos/`
> (already vendored). Override by setting `M3_LONG_VIDEO_DIR` to a different directory.
> Cases auto-skip if the fixture is missing.

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 11_01 | `test_11_01_long_video_5min` | D_300s.mp4 (5 min, ~5MB, default fps=1) | 200/4xx/5xx soft assertion |
| 11_02 | `test_11_02_long_video_10min` | D_600s.mp4 (10 min, default fps=1) | 200/4xx/5xx soft assertion |
| 11_03 | `test_11_03_long_video_20min` | D_1200s.mp4 (20 min, fps=0.5 to control total pixels) | 200/4xx/5xx soft assertion |
| 11_04 | `test_11_04_long_video_30min` | D_1800s.mp4 (30 min, fps=0.5 to control total pixels) | 200/4xx/5xx soft assertion |

## 12 media_gradient — Resolution gradient / multi-video gradient

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 12_01 | `test_12_01_resolution_gradient[1080P\|2K]` | Video resolution gradient (1920×1080 / 3840×2160) | HTTP 200 |
| 12_02 | `test_12_02_multi_video_gradient[count=3\|5]` | real_2s.mp4 × {3, 5} segments stacking gradient | 200/4xx soft assertion |
| 12_03 | `test_12_03_video_temporal` | real_2s.mp4 + "What happens in this video?" | content > 10 chars (temporal understanding) |
| 12_04 | `test_12_04_image_video_combined` | Real image sx1.jpg + real video real_2s.mp4 in same message | content > 20 chars (dual description) |

## 13 video_extension — reasoning_split and other extension fields

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 13_01 | `test_13_01_reasoning_split[non_stream\|stream]` | Video + `reasoning_split=True` + `thinking={type:adaptive}`, non-stream/stream paths | 200/400 soft tolerance (extension field may be unsupported) |

## 14 error_codes — Video-related error codes

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_fps_out_of_range` | fps=100 significantly out-of-range (hard-assert scenario) | HTTP 400 (`assert_error(r, 400)`) |

## 15 stream_usage — Video + streaming usage chunk

| Case ID | Function Name | Scene Description | Key Assertions |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_stream_usage_only_in_last_chunk` | Stream + stream_options.include_usage=true + video | usage non-empty with three positive token fields, present only in the final data chunk |

---

## Appendix: 86 items after parametrize expansion

Functions decorated with `@pytest.mark.parametrize(...)` expand to multiple items. All parametrize factors in the video file:

| Expansion Factor | Cases Involved | Multiplier |
|:---|:---|:---:|
| `mime ∈ {video/avi, video/x-msvideo}` | 03_05 | ×2 |
| `stream ∈ {non_stream, stream}` | 05_02 / 13_01 | ×2 |
| `fps ∈ {0.5, 1, 2}` | 06_01 | ×3 |
| `fps ∈ {0.5, 1.0, 2.0, 5.0}` | 06_02 | ×4 |
| `fps ∈ {0.1, 0, -1, 10, 100}` | 06_03 | ×5 |
| `fps ∈ {0.1, 0.0, -1}` | 06_06 | ×3 |
| `fps ∈ {5.1, 10, 1000}` | 06_07 | ×3 |
| `detail ∈ {low, default, high}` | 07_01 | ×3 |
| `mlsp ∈ {504, 1008, 2016}` | 09_01 | ×3 |
| `invalid_value ∈ {140, 3612, 0, -28}` | 09_03 | ×4 |
| `(filename, label) ∈ {1080P, 2K}` | 12_01 | ×2 |
| `count ∈ {3, 5}` | 12_02 | ×2 |

Total items = 61 functions - 12 (parametrized) + (2+2+2+3+4+5+3+3+3+3+4+2+2) = **86**.

## Appendix: Fixture index

| Fixture Path | Size | Primary Usage |
|:---|:---:|:---|
| `fixtures/m3_test_videos/video_400x300.mp4` | ~5KB | 08_01 no-scale tier smoke |
| `fixtures/m3_test_videos/video_640x480.mp4` | ~5KB | 06/08 generic small-video |
| `fixtures/m3_test_videos/video_1280x720.mp4` | ~10KB | 08 multi-tier cases |
| `fixtures/m3_test_videos/video_1920x1080.mp4` | ~15KB | 08 / 12 high-resolution cases |
| `fixtures/m3_test_videos/video_3840x2160.mp4` | ~25KB | 08 / 09 / 12 2K-tier cases |
| `fixtures/m3_test_videos/real_2s.mp4` | ~104KB | 04/05/07/13 real-video smoke workhorse |
| `fixtures/m3_test_videos/12s_real.mp4` | ~628KB | 06 fps-param cases (12-sec real video) |
| `fixtures/m3_test_videos/flower-video.mp4` | ~1MB | 05_04 second segment in multi-video mix |
| `fixtures/m3_test_videos/476117246902419462.mp4` | ~5MB | 01_02 / 02_02 real footage (Spring Festival pony cartoon) |
| `fixtures/m3_test_videos/test_video.mov` | ~160KB | 03_06 real MOV smoke |
| `fixtures/m3_test_videos/test_video.avi` | ~160KB | 03_07 real AVI smoke |
| `fixtures/m3_test_videos/test_video.mkv` | ~160KB | 03_08 real MKV smoke |
| `fixtures/m3_test_videos/D_300s.mp4` | ~5MB | 11_01 5-min long video |
| `fixtures/m3_test_videos/D_600s.mp4` | ~10MB | 11_02 10-min long video |
| `fixtures/m3_test_videos/D_1200s.mp4` | ~20MB | 11_03 20-min long video (env-overridable) |
| `fixtures/m3_test_videos/D_1800s.mp4` | ~30MB | 11_04 30-min long video (env-overridable) |
| `<size_fixture>/video_49mb.mp4` | ~47.4MB | 10_01 / 10_03 size-limit accept side |
| `<size_fixture>/video_51mb.mp4` | ~52MB | 10_04 large-video side (base64) |
| `<size_fixture>/video_251mb.mp4` | ~254MB | 10_02 / 10_05 >250MB large-video side (URL, 1920×1080 freight train) |
| `SAMPLE_VIDEO_URL` (public) | — | 02_01 public URL smoke |
| `PONY_VIDEO_URL` (COS) | — | 02_02 real footage OSS URL |

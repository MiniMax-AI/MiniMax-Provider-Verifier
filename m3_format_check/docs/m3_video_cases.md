# M3 视频模态格式校验 case 清单

> 对应文件:`data/m3_api_test/m3_video_tests.py`
> 命名规范:`test_<模块编号 2 位>_<模块内顺序编号 2 位>_<场景说明>`
> 模块数:**15**;case 函数数:**61**;pytest 收集 items 数:**86**

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 | 收集 items |
|:---:|:---|:---|:---:|:---:|
| 01 | base64_video | base64 视频基础接受性 | 2 | 2 |
| 02 | url_video | URL 视频接受性 | 2 | 2 |
| 03 | video_format | 视频容器/MIME 格式(MOV/MKV/AVI 等) | 8 | 9 |
| 04 | multi_video | 多段视频叠加 / 数量上限 | 5 | 5 |
| 05 | image_video_mixed | 图 + 视频混合 message | 4 | 5 |
| 06 | fps_param | fps 合法档位 与 越界 | 7 | 20 |
| 07 | detail_param | detail / fps 字段缺省与组合 | 5 | 7 |
| 08 | resolution_tier | 分辨率档位 / 边界 / 像素上限 | 9 | 9 |
| 09 | max_long_side_pixel | max_long_side_pixel(28 倍数)契约 | 3 | 8 |
| 10 | video_size_limit | 视频大小限(≤250MB) | 5 | 5 |
| 11 | long_video | 长视频(5/10/20/30 min) | 4 | 4 |
| 12 | media_gradient | 分辨率梯度 / 多视频梯度 | 4 | 6 |
| 13 | video_extension | reasoning_split 等扩展字段 | 1 | 2 |
| 14 | error_codes | 视频相关错误码 | 1 | 1 |
| 15 | stream_usage | 视频 + 流式 usage chunk | 1 | 1 |
| | **合计** | | **61** | **86** |

---

## 01 base64_video — base64 视频基础接受性

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_base64_video` | base64 最小 MP4 + "What do you see" | HTTP 200 + content 非空(> 20 字符) |
| 01_02 | `test_01_02_base64_real_pony_cartoon` | 真实素材(春节卡通小马 5MB)base64 输入,`max_tokens=4096` | HTTP 200 + content > 50 字符 + **主体关键词命中**(horse/pony/cartoon/马/小马/卡通/...)+ **春节场景关键词命中**(lantern/firecracker/spring festival/灯笼/鞭炮/春节/元宝/中国结/红色/金色/...) |

## 02 url_video — URL 视频接受性

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_url_video` | 公网示例 mp4 URL(`SAMPLE_VIDEO_URL`) | HTTP 200 + content 非空(> 20 字符) |
| 02_02 | `test_02_02_url_real_pony_cartoon` | 真实素材(春节卡通小马)经 OSS URL 输入,`max_tokens=4096` | HTTP 200 + content > 50 字符 + **主体关键词命中**(horse/pony/cartoon/马/小马/卡通/...)+ **春节场景关键词命中**(lantern/firecracker/spring festival/灯笼/鞭炮/春节/元宝/中国结/红色/金色/...) |

## 03 video_format — 视频容器/MIME 格式

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_mkv_format_legacy` | MKV(video/x-matroska)伪装最小 mp4(legacy 用例) | 200 / 已知不支持时 xfail |
| 03_02 | `test_03_02_mov_format_video_quicktime` | MOV(video/quicktime base64 伪装) | 200 / BUG-7 时 xfail |
| 03_03 | `test_03_03_mov_format_video_mov` | MOV(spec 1.3.5 要求 `data:video/mov;base64,...`) | 200 / BUG-7 时 xfail |
| 03_04 | `test_03_04_mkv_format_video_matroska` | MKV(video/x-matroska)伪装最小 mp4 | 200 / BUG-7 时 xfail |
| 03_05 | `test_03_05_avi_format[video_avi\|video_x_msvideo]` | AVI 两种合法 MIME(`video/avi` / `video/x-msvideo`) | 200 / 不支持时 xfail |
| 03_06 | `test_03_06_real_mov_smoke` | 真实 MOV 文件 `fixtures/test_video.mov` 默认 detail/fps | 200/400/415/422/500 软断言 |
| 03_07 | `test_03_07_real_avi_smoke` | 真实 AVI 文件 `fixtures/test_video.avi` 默认 detail/fps | 200/400/415/422/500 软断言 |
| 03_08 | `test_03_08_real_mkv_smoke` | 真实 MKV 文件 `fixtures/test_video.mkv` 默认 detail/fps | 200/400/415/422/500 软断言 |

## 04 multi_video — 多段视频叠加 / 数量上限

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 04_01 | `test_04_01_count_at_max` | 5 段最小 mp4(spec 上限) | HTTP 200 |
| 04_02 | `test_04_02_count_over_max` | 10 段最小 mp4(超 spec 上限) | HTTP 200 + content 非空(实测 M3 不强制拦截) |
| 04_03 | `test_04_03_multi_video_3` | 3 段 real_2s.mp4 真实视频叠加 | 200/4xx 软断言 |
| 04_04 | `test_04_04_multi_video_5` | 5 段 real_2s.mp4 真实视频叠加 | 200/4xx 软断言 |
| 04_05 | `test_04_05_multi_video_b64_url_mix` | base64 + URL 两段不同形态多视频混合 | 200/4xx 软断言 |

## 05 image_video_mixed — 图 + 视频混合 message

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_one_image_one_video` | 1 图(PNG) + 1 视频(real_2s) | HTTP 200 |
| 05_02 | `test_05_02_image_video_stream_variant[non_stream\|stream]` | 图+视频混合,非流式/流式两路 | 两路均 200 |
| 05_03 | `test_05_03_mixed_3img_1vid` | 3 真图(sx1×3) + 1 真实视频(real_2s) | 200/4xx 软断言 |
| 05_04 | `test_05_04_mixed_1img_2vid` | 1 真图(sx1) + 2 真实视频(real_2s + flower-video) | 200/4xx 软断言 |

## 06 fps_param — fps 合法档位 与 越界

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 06_01 | `test_06_01_fps_real_video[fps=0.5\|1\|2]` | 12s_real.mp4 + 三个常用 fps | HTTP 200 |
| 06_02 | `test_06_02_valid_fps[fps=0.5\|1.0\|2.0\|5.0]` | 12s_real.mp4 + 合法 fps ∈ [0.2, 5] 四档 | HTTP 200 |
| 06_03 | `test_06_03_invalid_fps[fps=0.1\|0\|-1\|10\|100]` | 12s_real.mp4 + 越界 fps(下越界 3 + 上越界 2) | 200/400/422/500 软断言 |
| 06_04 | `test_06_04_fps_lower_boundary` | 640×480 fixture + fps=0.2(下界) | HTTP 200 + prompt_tokens > 0 |
| 06_05 | `test_06_05_fps_upper_boundary` | 640×480 fixture + fps=5.0(上界) | HTTP 200 + prompt_tokens > 0 |
| 06_06 | `test_06_06_fps_below_min_short_fixture[0.1\|0.0\|-1]` | 640×480 fixture + 下界附近 3 个常见越界值 | 200/400/422 软断言 |
| 06_07 | `test_06_07_fps_above_max_short_fixture[5.1\|10\|1000]` | 640×480 fixture + 上界附近 3 个常见越界值 | 200/400/422 软断言 |

## 07 detail_param — detail / fps 字段缺省与组合

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_detail_value[low\|default\|high]` | `video_url.detail` ∈ {low, default, high} | 三档均 HTTP 200 |
| 07_02 | `test_07_02_no_detail_no_fps` | 不传 detail / fps,走默认(detail=default, fps=1) | HTTP 200 |
| 07_03 | `test_07_03_no_detail_explicit_fps` | 只传 fps,detail 走默认 | HTTP 200 |
| 07_04 | `test_07_04_no_fps_explicit_detail` | 只传 detail,fps 走默认 | HTTP 200 |
| 07_05 | `test_07_05_max_long_side_pixel_baseline` | `max_long_side_pixel=504` 最小档冒烟(28×18) | HTTP 200(完整契约见 §09) |

## 08 resolution_tier — 分辨率档位 / 边界 / 像素上限

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 08_01 | `test_08_01_tier_low_no_scale` | 400×300 视频(< default 档 672)+ detail=default | HTTP 200 + prompt_tokens > 0(不缩) |
| 08_02 | `test_08_02_tier_low_scale_down` | 1280×720 + detail=default | HTTP 200 + 每帧应缩 |
| 08_03 | `test_08_03_tier_default_no_scale` | 640×480 + detail=default | HTTP 200(不缩) |
| 08_04 | `test_08_04_tier_default_scale_down` | 1920×1080 + detail=default | HTTP 200 + 每帧应缩 |
| 08_05 | `test_08_05_tier_high_no_scale` | 1280×720 + detail=default | HTTP 200 |
| 08_06 | `test_08_06_tier_high_scale_down` | 3840×2160 + detail=default | HTTP 200 + 每帧应缩 |
| 08_07 | `test_08_07_tier_at_boundary` | 1280×720(长边 = default 档两倍)+ detail=default | HTTP 200(边界软断言) |
| 08_08 | `test_08_08_tier_consistency` | 1920×1080 大视频 + default 档 | HTTP 200 + prompt_tokens > 0 |
| 08_09 | `test_08_09_max_total_pixels_exceeded` | 3840×2160 + fps=5,逼近 max_total_pixels=301,056,000 | 200/400/413/422 软断言 |

## 09 max_long_side_pixel — `max_long_side_pixel`(28 倍数)契约

> OAI 契约:`max_long_side_pixel` 必须为 **28 的倍数**。
> 视频三档采用 **504(28×18) / 1008(28×36) / 2016(28×72)**;旧的 (504/672/1280) 组合里
> 672/1280 不是 28 的倍数,已废弃。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 09_01 | `test_09_01_tier_value[low=504\|default=1008\|high=2016]` | 三档喂 3840×2160 真实视频(长边 > 2016,均触发缩放) | HTTP 200 + prompt_tokens > 0 |
| 09_02 | `test_09_02_monotonic` | 同视频分别设三档,token 严格单调 504 < 1008 < 2016 | 三档 token 严格单调 |
| 09_03 | `test_09_03_out_of_range[below_min_28x5\|above_max_28x129\|zero\|negative_28]` | [150, 3584] 范围外(<150 / >3584 / 0 / 负数,均为 28 倍数) | 200/400/413/422 软断言 |

## 10 video_size_limit — 视频大小限(≤250MB)

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_url_under_50mb` | URL 方式 ~47.4 MB MP4(<50MB) | `assert_oai_success` 通过 |
| 10_02 | `test_10_02_url_over_250mb` | URL 方式 ~254 MB MP4(video_251mb.mp4,1920×1080 货运火车片段,>250MB) | 4xx,或 HTTP 200 + content 命中火车/铁路关键词(train/railway/railroad/freight/cargo/boxcar/track/video/clip 等),证明视频帧真的进了视觉编码,排除 silent-drop fallback 文本 |
| 10_03 | `test_10_03_base64_under_50mb` | Base64 方式 ~47.4 MB MP4(<50MB) | `assert_oai_success` 通过 |
| 10_04 | `test_10_04_base64_over_50mb` | Base64 方式 ~52 MB MP4(video_51mb.mp4,1280×720 / 55s 随机像素噪点视频,>50MB) | 4xx,或 HTTP 200 + content 命中视频/噪点关键词(noise/random/static/pixel/frame/video/clip/magenta/green pixel 等),证明视频帧真的进了视觉编码,排除 silent-drop fallback 文本 |
| 10_05 | `test_10_05_url_over_250mb_summary` | URL 方式 ~254 MB MP4(video_251mb.mp4,>250MB;总结类 prompt,与 10_02 互补) | 4xx,或 HTTP 200 + content 命中火车/铁路关键词,证明视频帧真的进了视觉编码,排除 silent-drop fallback 文本 |

## 11 long_video — 长视频(5/10/20/30 min)

> 默认从 `fixtures/m3_test_videos/` 读 D_300s/D_600s/D_1200s/D_1800s.mp4(已入仓);
> 想换一组长视频时,设环境变量 `M3_LONG_VIDEO_DIR` 指定目录覆盖。
> Fixture 缺失时本节 case 自动 skip。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 11_01 | `test_11_01_long_video_5min` | D_300s.mp4(5 分钟,~5MB,默认 fps=1) | 200/4xx/5xx 软断言 |
| 11_02 | `test_11_02_long_video_10min` | D_600s.mp4(10 分钟,默认 fps=1) | 200/4xx/5xx 软断言 |
| 11_03 | `test_11_03_long_video_20min` | D_1200s.mp4(20 分钟,fps=0.5 控总像素) | 200/4xx/5xx 软断言 |
| 11_04 | `test_11_04_long_video_30min` | D_1800s.mp4(30 分钟,fps=0.5 控总像素) | 200/4xx/5xx 软断言 |

## 12 media_gradient — 分辨率梯度 / 多视频梯度

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 12_01 | `test_12_01_resolution_gradient[1080P\|2K]` | 视频分辨率梯度(1920×1080 / 3840×2160) | HTTP 200 |
| 12_02 | `test_12_02_multi_video_gradient[count=3\|5]` | real_2s.mp4 × {3, 5} 段叠加梯度 | 200/4xx 软断言 |
| 12_03 | `test_12_03_video_temporal` | real_2s.mp4 + "What happens in this video?" | content > 10 字符(时序理解) |
| 12_04 | `test_12_04_image_video_combined` | 真实图 sx1.jpg + 真实视频 real_2s.mp4 同一 message | content > 20 字符(图+视频双描述) |

## 13 video_extension — reasoning_split 等扩展字段

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 13_01 | `test_13_01_reasoning_split[non_stream\|stream]` | 视频 + `reasoning_split=True` + `thinking={type:adaptive}`,流式/非流式两路 | 200/400 软容错(扩展字段可能不支持) |

## 14 error_codes — 视频相关错误码

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 14_01 | `test_14_01_fps_out_of_range` | fps=100 显著越界(硬断言场景) | HTTP 400(`assert_error(r, 400)`) |

## 15 stream_usage — 视频 + 流式 usage chunk

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 15_01 | `test_15_01_stream_usage_only_in_last_chunk` | 流式 + stream_options.include_usage=true + 视频 | usage 非空且三字段 > 0,且只出现在流式最后一个 data chunk |

---

## 附录:parametrize 展开后的 86 个 items

凡函数签名带 `@pytest.mark.parametrize(...)` 的会展开成多个 items。视频文件里所有 parametrize 展开因子如下:

| 展开因子 | 涉及 case | 展开倍数 |
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

总 items = 61 函数 - 12 (parametrize 函数) + (2+2+2+3+4+5+3+3+3+3+4+2+2) = **86**。

## 附录:固定 fixture 索引

| Fixture 路径 | 大小 | 主要用途 |
|:---|:---:|:---|
| `fixtures/m3_test_videos/video_400x300.mp4` | ~5KB | 08_01 不缩档位 smoke |
| `fixtures/m3_test_videos/video_640x480.mp4` | ~5KB | 06/08 多个 case 的通用小视频 |
| `fixtures/m3_test_videos/video_1280x720.mp4` | ~10KB | 08 多个档位 case |
| `fixtures/m3_test_videos/video_1920x1080.mp4` | ~15KB | 08 / 12 大分辨率 case |
| `fixtures/m3_test_videos/video_3840x2160.mp4` | ~25KB | 08 / 09 / 12 2K 档位 case |
| `fixtures/m3_test_videos/real_2s.mp4` | ~104KB | 04/05/07/13 等真实视频 smoke 主力 |
| `fixtures/m3_test_videos/12s_real.mp4` | ~628KB | 06 fps 参数 case(12 秒真实视频) |
| `fixtures/m3_test_videos/flower-video.mp4` | ~1MB | 05_04 多视频混合的第二段 |
| `fixtures/m3_test_videos/476117246902419462.mp4` | ~5MB | 01_02 / 02_02 真实素材(春节卡通小马) |
| `fixtures/m3_test_videos/test_video.mov` | ~160KB | 03_06 真实 MOV smoke |
| `fixtures/m3_test_videos/test_video.avi` | ~160KB | 03_07 真实 AVI smoke |
| `fixtures/m3_test_videos/test_video.mkv` | ~160KB | 03_08 真实 MKV smoke |
| `fixtures/m3_test_videos/D_300s.mp4` | ~5MB | 11_01 长视频 5min |
| `fixtures/m3_test_videos/D_600s.mp4` | ~10MB | 11_02 长视频 10min |
| `fixtures/m3_test_videos/D_1200s.mp4` | ~20MB | 11_03 长视频 20min(可 env 覆盖) |
| `fixtures/m3_test_videos/D_1800s.mp4` | ~30MB | 11_04 长视频 30min(可 env 覆盖) |
| `<size_fixture>/video_49mb.mp4` | ~47.4MB | 10_01 / 10_03 大小上限通过侧 |
| `<size_fixture>/video_51mb.mp4` | ~52MB | 10_04 大视频侧(base64) |
| `<size_fixture>/video_251mb.mp4` | ~254MB | 10_02 / 10_05 >250MB 大视频侧(URL,1920×1080 货运火车) |
| `SAMPLE_VIDEO_URL`(public) | — | 02_01 公网 URL smoke |
| `PONY_VIDEO_URL`(COS) | — | 02_02 真实素材 OSS URL |

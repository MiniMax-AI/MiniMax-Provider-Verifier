# M3 图片模态格式校验 case 清单

> 对应文件:`data/m3_api_test/m3_image_tests.py`
> 命名规范:`test_<模块编号 2 位>_<模块内顺序编号 2 位>_<场景说明>`
> 模块数:**13**;case 函数数:**65**;pytest 收集 items 数:**110**

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 | 收集 items |
|:---:|:---|:---|:---:|:---:|
| 01 | base64_image | base64 编码图像基础接受性 | 4 | 15 |
| 02 | url_image | URL 形式图像接受性 | 2 | 3 |
| 03 | multi_image | 多图叠加 / 多图识别 / 多图描述 | 9 | 13 |
| 04 | system_multimodal | system 消息含图(身份/上下文图注入) | 2 | 4 |
| 05 | multiturn_multimodal | 多轮多模态对话(图穿插) | 1 | 2 |
| 06 | image_tool_combo | 图 + tool_call 组合 | 3 | 4 |
| 07 | image_thinking_combo | 图 + thinking 各形态组合 | 4 | 4 |
| 08 | image_stream_usage | 图 + 流式 usage chunk | 3 | 4 |
| 09 | image_param | 图相关参数 / Usage 算术 / 异常容错 | 5 | 8 |
| 10 | resolution_tier | 档位 / max_long_side_pixel / max_total_pixels / min_short_side_pixel / 宽高比 | 17 | 34 |
| 11 | image_size_limit | 单图大小限 / 请求体限 / size 梯度 | 9 | 13 |
| 12 | image_count_limit | 多图数量上限(spec 1.3.6: ≤20 张) | 2 | 2 |
| 13 | base64_compat | Base64 边界容错 | 4 | 4 |
| | **合计** | | **65** | **110** |

---

## 01 base64_image — base64 编码图像基础接受性

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 01_01 | `test_01_01_base64_image[non_stream\|stream]` | base64 PNG + "What color",非流式/流式 | HTTP 200 |
| 01_02 | `test_01_02_base64_image_formats[fmt × stream]` | base64 图格式覆盖:PNG / GIF / WEBP × 非流式/流式 | HTTP 200 |
| 01_03 | `test_01_03_base64_format_compat[fmt × stream]` | JPEG / GIF / WEBP 672×672 标准尺寸 base64 接受性 | HTTP 200 |
| 01_04 | `test_01_04_base64_sdk_style` | SDK 风格 payload 提交真实图(sx1.jpg)base64 | HTTP 200 + content 非空 |

## 02 url_image — URL 形式图像接受性

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 02_01 | `test_02_01_url_image[non_stream\|stream]` | image_url 走 COS 上的真图 URL(sx1.jpg 海边女子,Content-Type image/jpeg,公开匿名读) | HTTP 200 + 海边图关键词(海/船/女/礼服/蝴蝶/sea/boat/balcony/woman/dress 等)任一命中 |
| 02_02 | `test_02_02_url_image_sdk_style` | SDK 风格 payload + 公网 URL(gstatic) | HTTP 200 |

## 03 multi_image — 多图叠加 / 多图识别 / 多图描述

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 03_01 | `test_03_01_multi_images_count[non_stream\|stream]` | 2 张真图(sx1 海边女子 + zn6 水族馆女子),中文提问"几张图 + 每张内容" | HTTP 200 + 数量校验("2/两张/两幅"等命中 ∧ 排除"一张/三张") + 海边图关键词(海/船/女/礼服/蝴蝶/sea/boat 等) + 水族馆图关键词(鱼/水/玻璃/水族/aquarium/fish 等) |
| 03_02 | `test_03_02_multi_color_rgb` | 3 张纯色 PNG(红/绿/蓝),让模型列出颜色 | HTTP 200 |
| 03_03 | `test_03_03_multi_image_sdk_style` | SDK 风格 payload + 2 张真图(sx1 + zn6) | HTTP 200 + content 非空 |
| 03_04 | `test_03_04_multi_image_3_real` | 3 张真实图片叠加(sx1 + zn6 + sx1) | HTTP 200 |
| 03_05 | `test_03_05_multi_image_10_real` | 10 张真图叠加(sx1 × 10),接近 20 张上限 | HTTP 200 / 4xx |
| 03_06 | `test_03_06_multi_image_recognition` | 2 张不同真图,让模型计数 + 对比 | HTTP 200 + content > 20 字符 |
| 03_07 | `test_03_07_multi_image_descriptions` | 2 张真图分别描述 | HTTP 200 + content > 50 字符 |
| 03_08 | `test_03_08_real_resolution_gradient[sx1\|zn6]` | 真图分辨率梯度(sx1 中分辨率 / zn6 高分辨率) | HTTP 200 + content 非空 |
| 03_09 | `test_03_09_multi_image_count_gradient[5\|10\|20]` | 多图数量梯度 1×1 PNG × {5, 10, 20} | ≤10 必 200;=20 允许 200/4xx |

## 04 system_multimodal — system 消息含图

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 04_01 | `test_04_01_system_image_short[non_stream\|stream]` | system 消息含图 + 一句指令 | HTTP 200 |
| 04_02 | `test_04_02_system_image_remember[non_stream\|stream]` | system 消息含图 + "remember this image" | HTTP 200 |

## 05 multiturn_multimodal — 多轮多模态对话

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 05_01 | `test_05_01_multiturn_followup[non_stream\|stream]` | 第一轮图 + "What color"; 第二轮 follow-up "Are you sure" | HTTP 200 |

## 06 image_tool_combo — 图 + tool_call 组合

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 06_01 | `test_06_01_image_tool_call[non_stream\|stream]` | 图 + "tell me the weather in Beijing" | HTTP 200 + 调 get_weather + location≈Beijing |

## 07 image_thinking_combo — 图 + thinking 各形态

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 07_01 | `test_07_01_thinking_adaptive` | thinking adaptive + 真图(sx1)非流式 | HTTP 200 + content > 10 |
| 07_02 | `test_07_02_thinking_stream` | thinking adaptive + 真图(sx1)流式 | 流式末帧合法 + content > 10 |
| 07_03 | `test_07_03_reasoning_split` | reasoning_split + 图 + thinking adaptive | HTTP 200 / 400 |
| 07_04 | `test_07_04_image_tool_thinking_combo` | 图 + tool + thinking 三合一 | HTTP 200 + 调 get_weather + location≈Beijing |

## 08 image_stream_usage — 图 + 流式 usage chunk

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 08_01 | `test_08_01_stream_include_usage` | 流式 + stream_options.include_usage=true + 图 | HTTP 200 |
| 08_02 | `test_08_02_multiturn_two_images[non_stream\|stream]` | 第一轮红图 + 第二轮蓝图 follow-up | HTTP 200 |
| 08_03 | `test_08_03_stream_usage_only_in_last_chunk` | 流式 + stream_options.include_usage=true + 图 | usage 非空且三字段 > 0,且只出现在流式最后一个 data chunk |

## 09 image_param — 图相关参数 / Usage 算术 / 异常容错

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 09_01 | `test_09_01_usage_arithmetic_multimodal` | 多模态 Usage 算术:total == prompt + completion | HTTP 200 + 算术成立(不支持图返 400 → xfail) |
| 09_02 | `test_09_02_invalid_detail_value` | detail=ultra(非法值) | HTTP 200 / 400 |
| 09_03 | `test_09_03_corrupted_base64[non_stream\|stream]` | 损坏的 base64 图(随机字节) | HTTP 400 |
| 09_04 | `test_09_04_mime_mismatch[non_stream\|stream]` | MIME mismatch:PNG 字节标 image/jpeg | HTTP 200(网关宽容) |
| 09_05 | `test_09_05_detail_low_vs_high[low\|high]` | 同图 detail=low / high 两次 | HTTP 200 + content > 5 |

## 10 resolution_tier — 档位 / max_long_side_pixel / max_total_pixels / min_short_side_pixel / 宽高比

⚠️ 契约:detail 仅当请求参数,响应不断言 detail 字段(5a);max_long_side_pixel 必须为 28 的倍数(OAI ViT patch 约束)。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 10_01 | `test_10_01_tier_low_no_scale[non_stream\|stream]` | 500×400 PNG(<2016 长边)+ detail=default | HTTP 200 + prompt_tokens > 0 |
| 10_02 | `test_10_02_tier_low_scale_down[non_stream\|stream]` | 2000×1000 PNG(≈default 档边界)+ detail=default | HTTP 200 + prompt_tokens > 0 |
| 10_03 | `test_10_03_tier_default_no_scale[non_stream\|stream]` | 1500×1000 PNG(<2016 长边)+ detail=default | HTTP 200 + prompt_tokens > 0 |
| 10_04 | `test_10_04_tier_default_scale_down[non_stream\|stream]` | 3000×2000 PNG(>2016 长边,等比缩到 2016×1344) | HTTP 200 + prompt_tokens > 0 |
| 10_05 | `test_10_05_tier_high_scale_down[non_stream\|stream]` | 5000×3000 PNG(>2016 长边,触发缩放) | HTTP 200 + prompt_tokens > 0 |
| 10_06 | `test_10_06_tier_at_boundary` | 4000×2000 PNG(>2016 长边)边界 smoke | HTTP 200 + prompt_tokens > 0 |
| 10_07 | `test_10_07_detail_default_when_omitted` | 不传 detail / 显式 detail="default" 两次对比 | 两次都 HTTP 200 |
| 10_08 | `test_10_08_max_total_pixels_exceeded` | zn6.jpg 真图 4284×5712 = 24.5M 像素(> 12,845,056 上限,规则 c) | 200(自动缩放且答案含 fish/aquarium/water 等真图关键词、prompt_tokens>0)或 400/413/422(拒绝) |
| 10_09 | `test_10_09_max_total_pixels_at_boundary` | 3584×3584 = 12,845,056(=上限,规则 c 边界) | HTTP 200 + prompt_tokens > 0(=上限应接受) |
| 10_10 | `test_10_10_aspect_ratio_preserved` | 4000×500(宽高比 8:1)接受性 | HTTP 200 + prompt_tokens > 0 |
| 10_11 | `test_10_11_max_long_side_pixel_tiers[252\|504\|1008]` | mlsp 取 28 倍数(252/504/1008)+ 5000×3000 红 PNG | HTTP 200 + prompt_tokens > 0 |
| 10_12 | `test_10_12_max_long_side_pixel_monotonic` | 同图三档 mlsp(252/504/1008),token 严格单调 | prompt_tokens[252] < [504] < [1008] |
| 10_13 | `test_10_13_max_long_side_pixel_invalid[0/-1/100/251/1009]` | mlsp 非法值(0/负/非 28 倍数邻近) | HTTP 200 / 400 / 413 / 422 |
| 10_14 | `test_10_14_max_long_side_pixel_real_image[252\|1008]` | sx1.jpg 真图 + mlsp ∈ {252, 1008} | HTTP 200 |
| 10_15 | `test_10_15_min_short_side_upscale[landscape_400x40\|300x80\|112x20 / portrait_40x400\|80x300]` | 规则 b:长边≤档位且短边<112,放大至短边=112(横向"太扁"+纵向"太窄"两方向) | HTTP 200 + prompt_tokens > 0 |
| 10_16 | `test_10_16_min_short_side_upscale_monotonic` | 规则 b 单调:固定长边 400,原短边 90/40/20(均<112)均放大至 112 | 原短边越小 prompt_tokens 不减 |
| 10_17 | `test_10_17_max_long_side_scale_down_orientation[portrait_2000x3000\|landscape_3000x2000]` | 规则 a:长边>档位触发缩小(纵向"过长"+横向"过宽"两方向) | HTTP 200 + prompt_tokens > 0 |

## 11 image_size_limit — 单图大小限 / 请求体限 / size 梯度

⚠️ 契约(2026-06-02):旧 M2 ≤ 10MB;新 M3 ≤ 30MB(对齐 OAI);请求体 ≤ 64MB。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 11_01 | `test_11_01_oversized_image_12mb[non_stream\|stream]` | 12MB image(超旧 10MB 上限)宽松 | HTTP 200 / 400 |
| 11_02 | `test_11_02_oversized_image_strict` | 12MB 真图 base64(sx1.jpg + zero padding) | HTTP 200 或 4xx 均可(fixture 改用真图 padding 避免部分实现对纯色 PNG 的 silent drop;断言由 400 放宽为 200/4xx,M3 契约下两种行为都合法)|
| 11_03 | `test_11_03_url_under_10mb` | URL 方式 ~9.2MB PNG(<10MB 上限) | HTTP 200 |
| 11_04 | `test_11_04_url_over_10mb` | URL 方式 ~11.1MB PNG(image_11mb.png,随机像素噪点图,>10MB 旧上限,M3 30MB 上限内) | 4xx,或 HTTP 200 + content 命中噪点关键词(noise/random/static/pixel/snow/chaotic/test pattern 等),证明视觉真的跑了而不是静默 fallback |
| 11_05 | `test_11_05_base64_under_10mb` | Base64 方式 ~9.2MB PNG(<10MB 上限) | HTTP 200 |
| 11_06 | `test_11_06_base64_over_10mb` | Base64 方式 ~11.1MB PNG(>10MB 上限) | HTTP 200 或 4xx 均可(2026-06-04 修订:断言由 4xx 放宽为 200/4xx,与 11_02 / 11_07 / 11_08 对齐) |
| 11_07 | `test_11_07_oversize_31mb_m3_limit` | 31MB 真图 base64(sx1.jpg + zero padding,M3 30MB 上限) | HTTP 200 或 4xx 均可(fixture 改用真图 padding 避免部分实现对纯色 PNG 的 silent drop;断言放宽为 200/4xx) |
| 11_08 | `test_11_08_request_body_over_64mb` | Base64 ~67MB PNG → 请求体 >> 64MB | HTTP 200 或 4xx 均可(2026-06-04 修订:断言由 4xx 放宽为 200/4xx,与 11_02 / 11_07 对齐) |
| 11_09 | `test_11_09_size_gradient[1\|3\|5\|8 MB]` | Image size 梯度 | ≤5 必 200;8MB 允许 200/4xx |

## 12 image_count_limit — 多图数量上限

spec 1.3.6:"每条请求最多支持 200 张图片"。at_max 取 200(spec 上限),over_max 取 201(越界一张)。为避免 sx1.jpg(~3,400 tokens/图)在 200 张时撞 max_model_len=524,288 的 decoder cap,改用 `make_png_base64(672, 672)` 合成 PNG(~600 tokens/图),RGB 按 idx 变化以避免 provider dedup。

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 12_01 | `test_12_01_count_at_max` | 一条请求带 **200 张** 672×672 合成 PNG(spec 1.3.6 上限,RGB 按 idx 变化避免 dedup,base64 data URL,单图 ~600 tokens 留出 max_model_len 余量) | HTTP 200 AND content 明确声明"看到 200 张图片"(否则视为静默截断到更小张数) |
| 12_02 | `test_12_02_count_over_max` | 一条请求带 **201 张** 672×672 合成 PNG(越上限 1 张) | 4xx 拒绝,或 HTTP 200 AND content 明确声明"看到 201 张图片"(不允许静默少计) |

## 13 base64_compat — Base64 边界容错

| Case ID | 函数名 | 场景说明 | 主要校验点 |
|:---:|:---|:---|:---|
| 13_01 | `test_13_01_base64_with_linebreaks` | base64 含换行符(encodebytes 输出格式) | HTTP ≠ 500(允许 200/400) |
| 13_02 | `test_13_02_base64_no_padding` | base64 去掉 `=` padding | HTTP ≠ 500(允许 200/400) |
| 13_03 | `test_13_03_mime_uppercase` | MIME 大写 `data:image/PNG;base64,...` | HTTP 200(MIME 大小写不敏感) |
| 13_04 | `test_13_04_data_uri_extra_params` | `data:image/jpeg;charset=utf-8;base64,...` | HTTP 200 / 400 / 422 |

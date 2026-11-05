# M3_1_Flash 请求字段契约 case 清单
> 对应文件:`m3_format_check/m3_1_flash_request_test.py`
> 命名规范:`test_<模块编号>_<字段名>`,每个请求字段一个参数化函数,参数 id 即 Case ID
> 模块数:**26**;Case 数:**130**(期望 200:116,期望 400:14)

## 校验口径

每条 Case 只在一个请求字段上偏离最小合法请求,校验传输层契约:

- **期望 200**:HTTP 200,`choices` 非空,`choices[0].message.role == "assistant"`
- **期望 400**:HTTP 400,且响应体不含 `choices`(非法字段应被拒绝,而不是被静默接受)

不校验生成文本、语言或能力是否生效,这些归行为类用例。请求经 `oai_chat_verbatim` 原样发送,helper 不注入输出预算、不改写 `stream`,保证"省略 / 显式 null / 非法类型"场景真实发出。

Case ID 前缀:`REQ-` 合法输入,`ERR-` 非法输入或边界受理,`RES-` 结构化 / 预测输出请求。

## 模块总览

| 模块编号 | 字段 | 主题 | Case 数 |
|:---:|:---|:---|:---:|
| 01 | `model` | model 字段 | 2 |
| 02 | `messages` | messages 结构与消息形态 | 17 |
| 03 | `messages[].content[type=image_url]` | image_url 图片输入 | 18 |
| 04 | `max_completion_tokens` | max_completion_tokens 输出预算 | 4 |
| 05 | `max_tokens` | max_tokens（旧字段） | 2 |
| 06 | `stop` | stop 停止序列 | 3 |
| 07 | `temperature` | temperature | 4 |
| 08 | `top_p` | top_p | 5 |
| 09 | `presence_penalty` | presence_penalty | 3 |
| 10 | `frequency_penalty` | frequency_penalty | 3 |
| 11 | `logit_bias` | logit_bias | 6 |
| 12 | `seed` | seed | 4 |
| 13 | `n` | n 候选数 | 2 |
| 14 | `reasoning_effort` | reasoning_effort | 9 |
| 15 | `logprobs` | logprobs | 1 |
| 16 | `response_format` | response_format 结构化输出 | 17 |
| 17 | `prediction` | prediction 预测输出 | 6 |
| 18 | `modalities` | modalities 输出模态 | 2 |
| 19 | `audio` | audio | 1 |
| 20 | `prompt_cache_key` | prompt_cache_key | 2 |
| 21 | `prompt_cache_options` | 缓存选项默认行为 | 1 |
| 22 | `web_search_options` | web_search_options | 5 |
| 23 | `metadata` | metadata | 3 |
| 24 | `store` | store | 3 |
| 25 | `user` | user（旧字段） | 2 |
| 26 | `service_tier` | service_tier | 5 |

---

## 01 model — model 字段

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-001 | 最小user字符串请求 | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-023 | model为数组 | `model=[]` | 400 |

## 02 messages — messages 结构与消息形态

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| ERR-027 | messages为空数组 | `[]` | 400 |
| ERR-026 | messages为null | `null` | 400 |
| ERR-029 | message元素为数值 | `[1]` | 400 |
| REQ-009 | 连续两个system消息不臆造交替限制 | `[{"role": "system", "content": "Reply in English."}, {"role": "system", "content": "Keep the answer short."}, {"role": "user", "content": "Hello"}]` | 200 |
| REQ-016 | 标准tool text数组结果 | `assistant tool_calls + tool content=[text part]` | 200 |
| ERR-030 | message缺role | `[{"content": "Hello"}]` | 400 |
| ERR-032 | role为null | `[{"role": null, "content": "Hello"}]` | 400 |
| REQ-003 | 多轮assistant正文历史 | `[{"role": "user", "content": "Remember the code A7."}, {"role": "assistant", "content": "Noted."}, {"role": "user", "content": "What is the code?"}]` | 200 |
| REQ-008 | 同角色不同participant name | `[{"role": "user", "name": "a", "content": "Please compare plan A."}, {"role": "user", "name": "b", "content": "Also compare plan B."}]` | 200 |
| REQ-015 | assistant refusal字段显式null | `[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hello", "refusal": null}, {"role": "user", "content": "Continue"}]` | 200 |
| REQ-012 | assistant text数组历史 | `[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": [{"type": "text", "text": "Hello."}]}, {"role": "user", "content": "Continue"}]` | 200 |
| REQ-014 | assistant refusal字段为字符串 | `[{"role": "user", "content": "Earlier request"}, {"role": "assistant", "content": "I cannot help with the earlier request.", "refusal": "I cannot help with the earlier request."}, {"role": "user", "content": "Please explain caching."}]` | 200 |
| REQ-148 | 模型窗口内长单条user输入 | `单条长 user 文本（约 8 万字符）` | 200 |
| REQ-149 | 模型窗口内103条长会话历史 | `51 组 user/assistant + 1 条 user，共 103 条` | 200 |
| REQ-010 | user多个text part | `[{"role": "user", "content": [{"type": "text", "text": "First paragraph."}, {"type": "text", "text": "Second paragraph, please summarize."}]}]` | 200 |
| REQ-011 | 字符串含中文emoji转义 | `[{"role": "user", "content": "输入有中文🙂、引号\"、反斜线\\和换行\n请简短回应。"}]` | 200 |
| REQ-024 | 空text字符串与空数组分开 | `[{"role": "user", "content": [{"type": "text", "text": ""}, {"type": "text", "text": "Please explain caching."}]}]` | 200 |

## 03 image_url — image_url 图片输入

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-020 | PNG图像data URL输入 | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}]` | 200 |
| REQ-019 | JPEG图像data URL输入 | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<JPEG data URL>"}}]}]` | 200 |
| REQ-021 | WEBP图像data URL输入 | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<WEBP data URL>"}}]}]` | 200 |
| REQ-022 | non-animated GIF图像data URL输入 | `[{"role": "user", "content": [{"type": "text", "text": "Describe the main color in the image."}, {"type": "image_url", "image_url": {"url": "<GIF data URL>"}}]}]` | 200 |
| REQ-028 | 两次相同图片输入不按格式去重 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "image_url", "image_url": {"url": "<PNG data ...` | 200 |
| REQ-025 | 只有图片没有文字 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}]` | 200 |
| REQ-027 | 两图混合URL与data URL | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<HTTPS image URL>"}}, {"type": "image_url", "image_url": {"url": "<PNG da...` | 200 |
| REQ-034 | 同消息逐图low和high | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "low"}}, {"type": "image_url", "image_url": {"...` | 200 |
| REQ-026 | text-image-text交错 | `[{"role": "user", "content": [{"type": "text", "text": "Look at this image first."}, {"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "text", "...` | 200 |
| REQ-030 | detail=low支持模型正向 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "low"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| REQ-031 | detail=high支持模型正向 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "high"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| ERR-041 | image_url对象缺url | `[{"role": "user", "content": [{"type": "image_url", "image_url": {}}]}]` | 400 |
| ERR-042 | image url不是字符串 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": 12}}]}]` | 400 |
| REQ-033 | detail省略默认auto | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |
| ERR-045 | system含图片part：受理 | `[{"role": "system", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>"}}]}, {"role": "user", "content": "Hello"}]` | 200 |
| REQ-023 | HTTPS图片输入 | `[{"role": "user", "content": [{"type": "text", "text": "Describe the image."}, {"type": "image_url", "image_url": {"url": "<HTTPS image URL>"}}]}]` | 200 |
| ERR-044 | detail显式null：按省略处理 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": null}}]}]` | 200 |
| REQ-029 | detail=auto支持模型正向 | `[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "<PNG data URL>", "detail": "auto"}}, {"type": "text", "text": "Describe the image."}]}]` | 200 |

## 04 max_completion_tokens — max_completion_tokens 输出预算

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-060 | 推理预算包含隐藏推理token | `{"max_completion_tokens": 32, "reasoning_effort": "low"}` | 200 |
| ERR-076 | max_completion_tokens为小数 | `{"max_completion_tokens": 8.5}` | 400 |
| REQ-061 | 不显式设置任何输出预算 | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| REQ-131 | max_completion_tokens显式null合法类型路径 | `{"max_completion_tokens": null}` | 200 |

## 05 max_tokens — max_tokens（旧字段）

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-132 | max_tokens显式null合法类型路径 | `{"max_tokens": null}` | 200 |
| REQ-062 | legacy max_tokens兼容模型正向 | `{"max_tokens": 64}` | 200 |

## 06 stop — stop 停止序列

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| ERR-081 | stop元素非字符串 | `{"stop": ["a", 1]}` | 400 |
| REQ-067 | 四个stop字符串数组 | `{"stop": ["#A#", "#B#", "#C#", "#D#"]}` | 200 |
| REQ-068 | stop显式null | `{"stop": null}` | 200 |

## 07 temperature — temperature

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-040 | temperature=0合法值 | `{"temperature": 0}` | 200 |
| REQ-041 | temperature=0.2合法值 | `{"temperature": 0.2}` | 200 |
| REQ-042 | temperature=2合法值 | `{"temperature": 2}` | 200 |
| REQ-125 | temperature显式null合法类型路径 | `{"temperature": null}` | 200 |

## 08 top_p — top_p

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| ERR-065 | top_p低于0 | `{"top_p": -0.1}` | 400 |
| ERR-066 | top_p高于1 | `{"top_p": 1.1}` | 400 |
| REQ-044 | top_p=0.1合法值 | `{"top_p": 0.1}` | 200 |
| REQ-045 | top_p=1合法值 | `{"top_p": 1}` | 200 |
| REQ-126 | top_p显式null合法类型路径 | `{"top_p": null}` | 200 |

## 09 presence_penalty — presence_penalty

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-049 | presence_penalty=-2合法值 | `{"presence_penalty": -2}` | 200 |
| REQ-050 | presence_penalty=0合法值 | `{"presence_penalty": 0}` | 200 |
| REQ-051 | presence_penalty=2合法值 | `{"presence_penalty": 2}` | 200 |

## 10 frequency_penalty — frequency_penalty

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-046 | frequency_penalty=-2合法值 | `{"frequency_penalty": -2}` | 200 |
| REQ-047 | frequency_penalty=0合法值 | `{"frequency_penalty": 0}` | 200 |
| REQ-048 | frequency_penalty=2合法值 | `{"frequency_penalty": 2}` | 200 |

## 11 logit_bias — logit_bias

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-052 | logit_bias=-100合法偏置 | `{"logit_bias": {"1000": -100}}` | 200 |
| REQ-053 | logit_bias=-1合法偏置 | `{"logit_bias": {"1000": -1}}` | 200 |
| REQ-054 | logit_bias=0合法偏置 | `{"logit_bias": {"1000": 0}}` | 200 |
| REQ-055 | logit_bias=1合法偏置 | `{"logit_bias": {"1000": 1}}` | 200 |
| REQ-056 | logit_bias=100合法偏置 | `{"logit_bias": {"1000": 100}}` | 200 |
| REQ-129 | logit_bias显式null合法类型路径 | `{"logit_bias": null}` | 200 |

## 12 seed — seed

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-063 | 相同seed的尽力确定性观察 | `2 次请求：{"seed": 42}` | 200 |
| REQ-064 | int64最小合法seed | `{"seed": -9223372036854775808}` | 200 |
| REQ-065 | int64最大合法seed | `{"seed": 9223372036854775807}` | 200 |
| REQ-133 | seed显式null合法类型路径 | `{"seed": null}` | 200 |

## 13 n — n 候选数

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-058 | n省略默认1 | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-074 | n为小数 | `{"n": 1.5}` | 400 |

## 14 reasoning_effort — reasoning_effort

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-071 | reasoning_effort=low支持档 | `{"reasoning_effort": "low"}` | 200 |
| REQ-072 | reasoning_effort=medium支持档 | `{"reasoning_effort": "medium"}` | 200 |
| REQ-073 | reasoning_effort=high支持档 | `{"reasoning_effort": "high"}` | 200 |
| REQ-074 | reasoning_effort=xhigh支持档 | `{"reasoning_effort": "xhigh"}` | 200 |
| REQ-075 | reasoning_effort=max支持档 | `{"reasoning_effort": "max"}` | 200 |
| REQ-134 | reasoning_effort显式null合法类型路径 | `{"reasoning_effort": null}` | 200 |
| REQ-077 | 两轮切换顶层effort | `2 次请求：{"reasoning_effort": "low"}` | 200 |
| REQ-076 | 省略effort采用模型默认 | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |
| ERR-083 | reasoning_effort错类型 | `{"reasoning_effort": ["low"]}` | 400 |

## 15 logprobs — logprobs

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-081 | logprobs=false | `{"logprobs": false}` | 200 |

## 16 response_format — response_format 结构化输出

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| RES-063 | request.response_format声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-064 | request.response_format.type声明形态与正向观测 | `{"response_format": {"type": "text"}}` | 200 |
| RES-145 | text不强求JSON | `{"response_format": {"type": "text"}}` | 200 |
| RES-146 | JSON mode正常完成只保证JSON | `{"response_format": {"type": "json_object"}}` | 200 |
| RES-065 | request.response_format.json_schema声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-066 | request.response_format.json_schema.name声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-067 | request.response_format.json_schema.description声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-068 | request.response_format.json_schema.schema声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-069 | request.response_format.json_schema.strict声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-070 | request.response_format.json_schema.schema.type声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-071 | request.response_format.json_schema.schema.properties声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-072 | request.response_format.json_schema.schema.required声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-073 | request.response_format.json_schema.schema.additionalProperties声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-148 | strict完整成功时验证实际schema | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-150 | JSON/schema长度截断单独分类 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"ans...` | 200 |
| RES-075 | request.response_format.json_schema.schema.properties.<name>.enum声明形态与正向观测 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "answer_card", "strict": true, "schema": {"type": "object", "properties": {"val...` | 200 |
| RES-169 | 输出标量、object、array与null的类型明确区分 | `{"response_format": {"type": "json_schema", "json_schema": {"name": "types_card", "strict": true, "schema": {"type": "object", "properties": {"s": ...` | 200 |

## 17 prediction — prediction 预测输出

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| RES-088 | request.prediction声明形态与正向观测 | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-089 | request.prediction.type声明形态与正向观测 | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-090 | request.prediction.content声明形态与正向观测 | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-091 | request.prediction.content[*].type声明形态与正向观测 | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-092 | request.prediction.content[*].text声明形态与正向观测 | `{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |
| RES-161 | 预测字符串与文本数组是独立合法入口 | `2 次请求：{"prediction": {"type": "content", "content": "print(a)\n"}}` | 200 |

## 18 modalities — modalities 输出模态

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-099 | 显式text输出模态 | `{"modalities": ["text"]}` | 200 |
| REQ-143 | modalities显式null合法类型路径 | `{"modalities": null}` | 200 |

## 19 audio — audio

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-144 | audio显式null合法类型路径 | `{"audio": null}` | 200 |

## 20 prompt_cache_key — prompt_cache_key

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-107 | 稳定prompt_cache_key重复请求 | `2 次请求：{"prompt_cache_key": "suite-prefix"}` | 200 |
| REQ-145 | prompt_cache_key显式null合法类型路径 | `{"prompt_cache_key": null}` | 200 |

## 21 prompt_cache_options — 缓存选项默认行为

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-108 | 省略缓存选项默认隐式 | `[{"role": "user", "content": "Explain caching in one sentence."}]` | 200 |

## 22 web_search_options — web_search_options

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-120 | CC搜索context=low | `{"web_search_options": {"search_context_size": "low"}}` | 200 |
| REQ-121 | CC搜索context=medium | `{"web_search_options": {"search_context_size": "medium"}}` | 200 |
| REQ-122 | CC搜索context=high | `{"web_search_options": {"search_context_size": "high"}}` | 200 |
| REQ-123 | CC搜索完整大致位置 | `{"web_search_options": {"user_location": {"type": "approximate", "approximate": {"city": "San Francisco", "country": "US", "region": "California", ...` | 200 |
| REQ-124 | CC搜索仅国家位置 | `{"web_search_options": {"user_location": {"type": "approximate", "approximate": {"country": "US"}}}}` | 200 |

## 23 metadata — metadata

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-086 | metadata一个键值 | `{"metadata": {"suite": "format-check"}, "store": true}` | 200 |
| REQ-088 | metadata空字符串值 | `{"metadata": {"case": ""}, "store": true}` | 200 |
| REQ-138 | metadata显式null合法类型路径 | `{"metadata": null}` | 200 |

## 24 store — store

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-089 | store=false | `{"store": false}` | 200 |
| REQ-090 | store=true | `{"store": true}` | 200 |
| REQ-139 | store显式null合法类型路径 | `{"store": null}` | 200 |

## 25 user — user（旧字段）

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-092 | legacy user字符串兼容 | `{"user": "synthetic-user-hash"}` | 200 |
| REQ-141 | user显式null合法类型路径 | `{"user": null}` | 200 |

## 26 service_tier — service_tier

| Case ID | 场景说明 | 关键请求 | 期望 |
|:---:|:---|:---|:---:|
| REQ-093 | service_tier=auto授权路径 | `{"service_tier": "auto"}` | 200 |
| REQ-094 | service_tier=default授权路径 | `{"service_tier": "default"}` | 200 |
| REQ-095 | service_tier=flex授权路径 | `{"service_tier": "flex"}` | 200 |
| REQ-096 | service_tier=priority授权路径 | `{"service_tier": "priority"}` | 200 |
| REQ-142 | service_tier显式null合法类型路径 | `{"service_tier": null}` | 200 |

# M2-Her 兼容性格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_compat_tests.py`](../m2_her_compat_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**1**；case 函数数：**12**；pytest 收集 items 数：**49**
> 预期值：取自 MiniMax 官方接口的实测结果（2026-11-05/06）；判定规则见 [README](../README.md)。
> “请求失败”：HTTP 状态码非 200，或 HTTP 200 但响应中业务码非 0 / 带 error 对象，且没有返回回复内容；不比对具体的错误码和错误信息。
> 下表是内置基线。S / F / E 的完整定义及 PASS / FAIL / SKIP 边界见 [统一判定规则](../README.md#verdict-rules)。F 的非 200 包括 5xx；E 明确禁止 5xx。网络异常不算预期拒绝，损坏的 JSON / SSE 不能通过。

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 15 | compat | 调用方式、旧参数、额外参数与流式分包 | 12 |

---

## 15 compat — 调用方式、旧参数、额外参数与流式分包

预期拒绝或允许两种结果的分支，先用相同端点、模型、凭据和流式设置做正常对照。对照不成功，目标用例记为 SKIP。

| Case ID | 函数名 | 结果规则 | 场景说明 | 主要校验点 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 15_01 | [`test_15_01_endpoint_sdk_compatibility`](../m2_her_compat_tests.py#L37) | [S：必须成功](../README.md#verdict-rules) | 同一段对话含七种消息角色，每条都填了名字。用原生 HTTP、OpenAI 兼容 HTTP 和 OpenAI SDK 各发送一次整段回复、一次流式回复。 | 原生配置下六个组合都须成功；OpenAI 配置只测兼容 HTTP 与 SDK 的四个组合，另外两项跳过且不发送请求。SDK 读出的正文须与底层响应一致。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_02 | [`test_15_02_legacy_token_parameters`](../m2_her_compat_tests.py#L66) | [S：必须成功](../README.md#verdict-rules) | 让模型续写长故事。先只给旧长度参数，再让新旧参数各自取较小值，看哪个真正限制输出。 | 仅旧字段 16 须截在 16；旧 32、新 8 须截在 8；旧 8、新 32 可截在 32，也可自然停在 9–32。每支最多三个提示，均须有生成 token 计数。三次均合法但没有测出限额或优先级则 SKIP，计数缺失或错误则 FAIL。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_03 | [`test_15_03_completion_limit_above_2048`](../m2_her_compat_tests.py#L88) | [F：必须失败](../README.md#verdict-rules) | 把新参数 max_completion_tokens 设为 2049 或 4096，两个值都超过上限 2048。 | 内置基线要求两次都被拒绝。如果供应商明确采用“接受但封顶”的覆盖规则，则必须实际验证截断在 2048。三个合法提示都没能触及上限则 SKIP，缺少或违反必要计数则 FAIL。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_04 | [`test_15_04_empty_and_name_only_messages`](../m2_her_compat_tests.py#L117) | [按变体区分，见校验点](../README.md#verdict-rules) | 分别发送空消息列表、正文为空的 user、正文只有空白的 user、只有名字的 system 后接 user、只有 system 的对话。 | 空列表、空 user 正文和只有 system 都须拒绝。纯空白可以接受或拒绝，但 5xx 失败。只有名字的 system 后接正常 user 须成功。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_05 | [`test_15_05_role_order_and_sample_pairing`](../m2_her_compat_tests.py#L149) | [按变体区分，见校验点](../README.md#verdict-rules) | 分别尝试连续的 user、连续的 assistant、只有一方的示例消息、两个未命名 system，以及把未命名 group 和 user_system 放在 user 后面。 | 连续 user 或连续 assistant 须成功；单边示例可成功或拒绝，5xx 失败；所列两种未命名的组合须拒绝。混排同时改变了角色顺序和名字，不能单独判断是哪一项导致拒绝。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_06 | [`test_15_06_stream_extensions`](../m2_her_compat_tests.py#L190) | [S：必须成功](../README.md#verdict-rules) | 分别省略 stream_options、把 include_usage 打开、再把它关闭，观察能否正常回答、有没有报告用量。 | 三次都须成功。原生接口三次均须有 usage；OpenAI 接口只有打开开关时才有。逐包检查所有非 null 的用量，包括早期包。只有自定义规则指定 usage_only_last 时才限定仅末包报告。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_07 | [`test_15_07_undeclared_parameters`](../m2_her_compat_tests.py#L246) | [E：成功或失败，禁 5xx](../README.md#verdict-rules) | 给普通请求分别加一个扩展参数：tools、tool_choice、thinking、reasoning_split、reasoning_effort、response_format、seed、stop。 | 每次都可以正常回复或明确拒绝；5xx 失败。接口忽略参数也可通过，所以这一项无法证明工具调用、推理或其他功能生效。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_08 | [`test_15_08_stream_packet_quality`](../m2_her_compat_tests.py#L259) | [S：必须成功](../README.md#verdict-rules) | 分别请模型写游记和生成 JSON 列表。每个任务至少请求 3 次；合计未满 1000 字符就带上已有回复续写，最多 50 次，每次最多 2048 token。 | 按每个响应里的非空文本增量计算：首包最多 6 字符，中间包至少 5 字符，每包最多 512 字符。任一违规立即失败；50 次仍未凑够样本则 SKIP。只测分包，不评游记质量、JSON 格式或延迟。 | 需 --run-compat；预期值可用 --contract 文件替换；需 --run-slow |
| 15_09 | [`test_15_09_legacy_narrator`](../m2_her_compat_tests.py#L319) | [S：必须成功](../README.md#verdict-rules) | 在主角的 system 消息外，再给“旁白”一条 system 消息，然后加入用户设定和提问；每条消息都标明名字。 | 一次整段返回、一次流式返回；两次都须有格式正确的非空回答。回答是否用了旁白口吻不参与判定。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_10 | [`test_15_10_legacy_suggest_reply`](../m2_her_compat_tests.py#L336) | [S：必须成功](../README.md#verdict-rules) | 旅行对话末尾加一条名为“推荐回复”的空 user 消息。分别试有示例和无示例两种对话。 | 每种对话都测整段返回和流式返回，四次都须给出格式正确的非空回答。句数和建议的内容不参与判定。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_11 | [`test_15_11_legacy_named_group_chat`](../m2_her_compat_tests.py#L361) | [F：必须失败](../README.md#verdict-rules) | 分别用两条带名字的 system 设置角色 A、B，再让角色 A 向角色 B 打招呼。 | 整段和流式两种请求都须拒绝。此处只判断这组三条消息；15_09 的旁白输入另有不同预期。 | 需 --run-compat；预期值可用 --contract 文件替换 |
| 15_12 | [`test_15_12_legacy_token_boundaries`](../m2_her_compat_tests.py#L375) | [按变体区分，见校验点](../README.md#verdict-rules) | 把旧参数 max_tokens 设为 −1、0、1，分别测整段和流式；预算为 1 时请模型续写。 | −1、0 允许成功或拒绝，5xx 失败。预算 1 须成功，三次续写内须实际截断且 completion_tokens=1，可无正文。OpenAI 流式会显式请求用量。三个合法提示均未截断则 SKIP，缺少或违反必要计数则 FAIL。 | 需 --run-compat；预期值可用 --contract 文件替换 |

---

## 附录：parametrize 展开后的 49 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `variant(3) × stream(2)` | 15_01 |
| `variant,limits(3)` | 15_02 |
| `limit(2)` | 15_03 |
| `variant(5)` | 15_04 |
| `variant(6)` | 15_05 |
| `variant(3)` | 15_06 |
| `parameter,value(8)` | 15_07 |
| `variant(2)` | 15_08 |
| `stream(2)` | 15_09 / 15_11 |
| `samples(2) × stream(2)` | 15_10 |
| `limit(3) × stream(2)` | 15_12 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。

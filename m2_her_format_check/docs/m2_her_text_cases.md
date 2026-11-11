# M2-Her 文本与角色格式校验 case 清单

> 对应文件：[`m2_her_format_check/m2_her_text_tests.py`](../m2_her_text_tests.py)
> 命名规范：`test_<模块编号>_<模块内顺序编号>_<场景说明>`
> 模块数：**17**；case 函数数：**80**；pytest 收集 items 数：**343**

每行先说明供应商会收到什么，再说明看到什么结果才算通过。除特别标注外，本表面向 MiniMax 原生接口。运行条件列中的开关用于主动开启行为、兼容或长输入测试。

S 要求成功作答，F 要求请求被拒绝且无回复正文，E 允许成功或拒绝但不接受 HTTP 5xx。拒绝和允许两种结果的分支先检查同配置下的正常请求，复用本次运行中对应的前测结果。前测不通记 SKIP；用例内另有对照步骤时，以该行说明为准。不同供应商可用各自的错误码和文案。网络异常、损坏的 JSON 或 SSE 都不能当作正确拒绝。[完整判定和配置说明](../README.md#verdict-rules)

## 模块总览

| 模块编号 | 模块名 | 主题 | 函数数 |
|:---:|:---|:---|:---:|
| 01 | basic_text | 基础文本 | 6 |
| 02 | system_persona | system 人设 | 4 |
| 03 | user_system | user_system 用户设定 | 3 |
| 04 | group | group 场景 | 3 |
| 05 | sample_messages | 示例对话 sample_message_* | 4 |
| 06 | names | name 字段 | 4 |
| 07 | multiturn | 多轮对话 | 6 |
| 08 | sampling | 采样参数（temperature / top_p） | 5 |
| 09 | completion_limit | 输出长度上限 max_completion_tokens | 5 |
| 10 | response_usage | 响应结构与 usage | 7 |
| 11 | error_codes | 错误处理 | 9 |
| 12 | long_context | 长输入与 64K 上下文 | 4 |
| 13 | role_combo | 七种角色组合 | 5 |
| 16 | guide_alignment | 官网指南中的写法 | 2 |
| 17 | candidate_count | n 多条回复 | 8 |
| 18 | request_metadata | metadata / user / mask_sensitive_info | 3 |
| 19 | language_consistency | 回复语言 | 2 |

---

## 01 basic_text — 基础文本

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 01_01 | [`test_01_01_minimal_user_message`](../m2_her_text_tests.py#L72) | [S：必须成功](../README.md#verdict-rules) | 只发一条用户消息，请助手回答 OK。不给角色设定、说话人名字或采样参数，输出上限设为 128 token。 | 两种返回方式都应给出一条有正文的助手回复。回复写了别的词也能通过。 | 默认运行 |
| 01_02 | [`test_01_02_system_user_chat`](../m2_her_text_tests.py#L76) | [S：必须成功](../README.md#verdict-rules) | 把助手设定为“友好的助手”，再由用户说“你好”。 | 这两条消息应能一起提交并得到非空回答。回复的语气由模型决定。 | 默认运行 |
| 01_03 | [`test_01_03_chinese_text`](../m2_her_text_tests.py#L83) | [S：必须成功](../README.md#verdict-rules) | 请助手用中文写一句简短的问候。 | 回复至少有一个基本汉字，且没有乱码替换符 U+FFFD。例如“你好”符合条件；只写 Hello 不符合。 | 需 --run-behavior（模型行为，单独统计） |
| 01_04 | [`test_01_04_english_text`](../m2_her_text_tests.py#L95) | [S：必须成功](../README.md#verdict-rules) | 用英文请求一句纯英文问候。 | 回复至少含一个 A–Z 或 a–z 字母，且没有基本汉字。这个规则也可能接受其他使用拉丁字母的语言。 | 需 --run-behavior（模型行为，单独统计） |
| 01_05 | [`test_01_05_text_escaping_unicode`](../m2_her_text_tests.py#L106) | [S：必须成功](../README.md#verdict-rules) | 发一条带引号、反斜杠、换行和两个 emoji 的用户消息，请模型照抄。 | 服务应接受这段文字并返回能完整解码的非空回答；模型漏抄一个符号也可能通过。 | 默认运行 |
| 01_06 | [`test_01_06_multilingual_input`](../m2_her_text_tests.py#L122) | [S：必须成功](../README.md#verdict-rules) | 五次输入分别包含日文、韩文、阿拉伯文、俄文和用组合重音符号拼写的 Café。 | 每种输入在流式和非流式下都能得到非空回复。无需翻译原文，也不指定回答的语言。 | 默认运行 |

## 02 system_persona — system 人设

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 02_01 | [`test_02_01_system_identity`](../m2_her_text_tests.py#L134) | [S：必须成功](../README.md#verdict-rules) | 只在 system 消息里写助手身份编号 AI_K72，再让用户问“你的编号是什么”。 | 回复中须出现 AI_K72；编号前后可以有其他文字。 | 需 --run-behavior（模型行为，单独统计） |
| 02_02 | [`test_02_02_system_reply_prefix`](../m2_her_text_tests.py#L144) | [S：必须成功](../README.md#verdict-rules) | 在 system 消息里要求每次回复都以 HER_REPLY: 起头，再让用户打招呼。 | 正文第一个字符起就应是 HER_REPLY:；前面加空格、说明或代码块都会失败。 | 需 --run-behavior（模型行为，单独统计） |
| 02_04 | [`test_02_04_system_identity_multiturn`](../m2_her_text_tests.py#L155) | [S：必须成功](../README.md#verdict-rules) | 先给助手编号 AI_K72，在后面放入五轮与身份无关的历史问答，最后再问编号。 | 回复仍须包含最初 system 消息中的 AI_K72。 | 需 --run-behavior（模型行为，单独统计） |
| 02_05 | [`test_02_05_system_identity_isolation`](../m2_her_text_tests.py#L167) | [S：必须成功](../README.md#verdict-rules) | 先后发两个独立请求，分别给助手编号 AI_K72 和 AI_B19。两次问法相同。 | 第一次只能提到这两个编号中的 AI_K72，第二次只能提到 AI_B19；其他文字不限。 | 需 --run-behavior（模型行为，单独统计） |

## 03 user_system — user_system 用户设定

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 03_01 | [`test_03_01_user_system_identity`](../m2_her_text_tests.py#L181) | [S：必须成功](../README.md#verdict-rules) | 在一条没有 name 的 user_system 消息中写用户编号 USER_P38，然后问“我的编号是什么”。 | 答案须包含 USER_P38。这组消息本身应被接受。 | 需 --run-behavior（模型行为，单独统计） |
| 03_03 | [`test_03_03_user_system_multiturn`](../m2_her_text_tests.py#L192) | [S：必须成功](../README.md#verdict-rules) | 在 user_system 中指定用户的小组编号 TEAM_L63，接五轮其他问答，最后问“小组编号是什么”。 | 回复须从较早的用户设定中找出 TEAM_L63。 | 需 --run-behavior（模型行为，单独统计） |
| 03_04 | [`test_03_04_user_system_omitted`](../m2_her_text_tests.py#L203) | [S：必须成功](../README.md#verdict-rules) | 只发“你是助手”的 system 消息和用户问候，整个请求省略 user_system。 | 服务应能正常回答这类无用户设定的普通对话。 | 默认运行 |

## 04 group — group 场景

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 04_01 | [`test_04_01_group_scene_name`](../m2_her_text_tests.py#L214) | [S：必须成功](../README.md#verdict-rules) | 在一条没有 name 的 group 消息里指定场景 SCENE_R64，让用户问“现在是什么场景”。 | 助手应答出 SCENE_R64。只有这里的场景消息含有答案。 | 需 --run-behavior（模型行为，单独统计） |
| 04_02 | [`test_04_02_group_scene_isolation`](../m2_her_text_tests.py#L229) | [S：必须成功](../README.md#verdict-rules) | 发两个独立请求，将场景由 SCENE_R64 换成 SCENE_N21，提问保持不变。 | 每次都要答出自己请求里的场景编号，并且不能带出另一次的编号。 | 需 --run-behavior（模型行为，单独统计） |
| 04_03 | [`test_04_03_group_omitted`](../m2_her_text_tests.py#L243) | [S：必须成功](../README.md#verdict-rules) | 用户直接问助手一个问题，消息列表中不放 group。 | 应得到普通回答，说明这类单人对话可省略场景说明。 | 默认运行 |

## 05 sample_messages — 示例对话 sample_message_*

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 05_01 | [`test_05_01_single_sample_pair`](../m2_her_text_tests.py#L249) | [S：必须成功](../README.md#verdict-rules) | 给一组带名字的示例（用户 apple，助手 RESULT:APPLE），再让真实用户说 lemon。 | 这种“示例在前、真实消息在后”的排列应能得到回复；没有要求照着示例写大写字母。 | 默认运行 |
| 05_02 | [`test_05_02_three_sample_pairs`](../m2_her_text_tests.py#L258) | [S：必须成功](../README.md#verdict-rules) | 依次给 apple、pear、plum 三组带名字的示例，再提交真实用户的 lemon。 | 服务可以接收多组示例并回答当前请求。回复内容是否模仿这些示例不影响本项结果。 | 默认运行 |
| 05_04 | [`test_05_04_sample_vs_current_question`](../m2_her_text_tests.py#L268) | [按变体区分，见校验点](../README.md#verdict-rules) | 示例中处理 apple，真实用户提交 kiwi。一组给所有消息带上 name，另一组去掉所有 name。 | 全具名时须回答出 kiwi（忽略大小写）。无名组合须被拒绝；用同内容的具名组合确认服务可用，对照不通则记 SKIP。 | 需 --run-behavior（模型行为，单独统计） |
| 05_05 | [`test_05_05_samples_with_real_history`](../m2_her_text_tests.py#L291) | [S：必须成功](../README.md#verdict-rules) | 先放两组教学示例，再放真实的 mango 问答记录，最后让用户问 kiwi。每条消息都有名字。 | 示例、真实历史和新提问能混在同一请求中并得到非空回答即可。 | 默认运行 |

## 06 names — name 字段

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 06_01 | [`test_06_01_name_omitted`](../m2_her_text_tests.py#L304) | [S：必须成功](../README.md#verdict-rules) | 只给一条 user 消息，省略说话人的 name。 | 普通单用户请求可以成功；服务不能因为缺名字而拒绝。 | 默认运行 |
| 06_02 | [`test_06_02_name_unicode`](../m2_her_text_tests.py#L311) | [S：必须成功](../README.md#verdict-rules) | 三次把 name 分别设为小林、Alice、Zoë🙂，请模型说出发送者的名字。 | 三种名字都能提交并得到回复。服务接受该字符串就能通过，模型是否正确读出名字另测。 | 默认运行 |
| 06_03 | [`test_06_03_multiple_named_users`](../m2_her_text_tests.py#L321) | [S：必须成功](../README.md#verdict-rules) | 两位用户各报一个编号。先让 Alice 报 PASS_A17、Bob 报 PASS_B29，再对调发送者名字，编号出现的顺序不变。 | 两次回复都必须是可解析的 JSON 对象，恰好把 Alice 和 Bob 映射到各自编号。把两人的值答反、加代码块或解释都会失败。 | 需 --run-behavior（模型行为，单独统计） |
| 06_04 | [`test_06_04_multiple_named_assistants`](../m2_her_text_tests.py#L343) | [S：必须成功](../README.md#verdict-rules) | 把 NOTE_A17 和 NOTE_B29 分别写进 Alpha 和 Beta 的助手历史消息，再调换这两位助手的名字。 | 两次回复都须是只含 Alpha、Beta 两个键的 JSON 对象，各自的记录值与本次历史一致。 | 需 --run-behavior（模型行为，单独统计） |

## 07 multiturn — 多轮对话

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 07_01 | [`test_07_01_two_turn_memory`](../m2_her_text_tests.py#L366) | [S：必须成功](../README.md#verdict-rules) | 先告诉助手用户编号 HER_M41，放入助手确认消息，再问“我的编号是什么”。 | 回复中须出现上一轮的 HER_M41，允许带说明文字。 | 需 --run-behavior（模型行为，单独统计） |
| 07_02 | [`test_07_02_five_turn_facts`](../m2_her_text_tests.py#L378) | [S：必须成功](../README.md#verdict-rules) | 依次写入五条不同的记录，最后只问第 0 条和第 4 条的值。每个值都在对应的历史消息中给出。 | 必须同时答出 CEDAR_87 和 FERN_24。编号本身推不出记录值；只命中最后一条会失败。 | 需 --run-behavior（模型行为，单独统计） |
| 07_03 | [`test_07_03_twenty_turn_history`](../m2_her_text_tests.py#L387) | [S：必须成功](../README.md#verdict-rules) | 把历史加长到二十轮，让模型找出第 0 条和第 19 条记录。 | 必须同时答出首条 CEDAR_87 和末条 MOSS_36；问题本身只给位置，不给记录值。 | 需 --run-behavior（模型行为，单独统计） |
| 07_04 | [`test_07_04_actual_response_roundtrip`](../m2_her_text_tests.py#L395) | [S：必须成功](../README.md#verdict-rules) | 第一轮请助手确认编号，把收到的真实回复原样放进第二轮的 assistant 历史，再问编号。 | 两次都应成功。从接口拿到的文字必须能再当作历史提交；第二次答出什么编号不影响本项。 | 默认运行 |
| 07_05 | [`test_07_05_latest_fact_correction`](../m2_her_text_tests.py#L407) | [S：必须成功](../README.md#verdict-rules) | 历史中先写 OLD_K19，后来用户明确更正成 NEW_T83，最后只问更正后的编号。 | 回复要出现 NEW_T83 并排除 OLD_K19；把新旧编号并列也会失败。 | 需 --run-behavior（模型行为，单独统计） |
| 07_06 | [`test_07_06_conversation_isolation`](../m2_her_text_tests.py#L421) | [S：必须成功](../README.md#verdict-rules) | 分别发两段独立的对话历史，暗号各为 CODE_A17 和 CODE_B29；两个用户都问自己的暗号。 | 每次回答只可包含这两个暗号中的当前值。第二次重复第一次的暗号会失败。 | 需 --run-behavior（模型行为，单独统计） |

## 08 sampling — 采样参数（temperature / top_p）

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 08_01 | [`test_08_01_sampling_omitted`](../m2_her_text_tests.py#L435) | [S：必须成功](../README.md#verdict-rules) | 发同一条简短问题，请求体同时省略 temperature 和 top_p。 | 接口可以用自己的默认采样设置给出有效回复。测试不会推断这两个默认值是多少。 | 默认运行 |
| 08_02 | [`test_08_02_temperature_valid`](../m2_her_text_tests.py#L440) | [S：必须成功](../README.md#verdict-rules) | 在普通非流式请求中，分别将 temperature 设为 0.01、0.5、1.0。 | 三次都必须成功。这验证这些数值可用；生成文字的随机程度不参与评分。 | 默认运行 |
| 08_03 | [`test_08_03_temperature_invalid`](../m2_her_text_tests.py#L449) | [按变体区分，见校验点](../README.md#verdict-rules) | 分别把温度设为数字 0、−0.1、1.01、字符串“0.5”或布尔值 true。 | 0、1.01 可正常回答或明确拒绝，但遇到 5xx 就失败（E）。负数、字符串和布尔值必须被拒绝（F）。 | 默认运行 |
| 08_04 | [`test_08_04_top_p_valid`](../m2_her_text_tests.py#L462) | [S：必须成功](../README.md#verdict-rules) | 在普通非流式请求中，分别将 top_p 设为 0.01、0.5、0.95、1.0。 | 四个有效值都须得到正常回复，其中也包括上边界 1.0。 | 默认运行 |
| 08_05 | [`test_08_05_top_p_invalid`](../m2_her_text_tests.py#L471) | [按变体区分，见校验点](../README.md#verdict-rules) | 分别提交 top_p 为 0、−0.1、1.01、字符串“0.95”和布尔值 true 的请求。 | 0 可接受或拒绝，5xx 失败（E）。−0.1、1.01 及两种错误类型均须被拒绝（F）。 | 默认运行 |

## 09 completion_limit — 输出长度上限 max_completion_tokens

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 09_01 | [`test_09_01_completion_limit_omitted`](../m2_her_text_tests.py#L485) | [S：必须成功](../README.md#verdict-rules) | 把新旧两个输出额度字段 max_completion_tokens 和 max_tokens 都从请求体拿掉。 | 服务应返回有效回答，不要求实际输出达到某个默认额度。 | 默认运行 |
| 09_02 | [`test_09_02_completion_limit_valid`](../m2_her_text_tests.py#L492) | [S：必须成功](../README.md#verdict-rules) | 用同一个简短问题分别请求 1、2、32、2047 和 2048 个输出 token。 | 回复须有完整用量且加总正确。输出不超过请求额度，报告 length 时须恰好用完；仅 1 token 时正文可空，缺计数直接失败。 | 默认运行 |
| 09_03 | [`test_09_03_completion_limit_nonpositive`](../m2_her_text_tests.py#L500) | [E：成功或失败，禁 5xx](../README.md#verdict-rules) | 分别请求 0 个和 −1 个输出 token。 | 非正额度可以被拒绝，也可以得到结构正确的回复（可为空）；HTTP 5xx 失败。服务如何解释这个额度不作要求。 | 默认运行 |
| 09_04 | [`test_09_04_completion_limit_type`](../m2_her_text_tests.py#L513) | [按变体区分，见校验点](../README.md#verdict-rules) | 把输出额度依次写成 1.5、字符串“32”、布尔值 true 和 null。 | 前三种类型均须被拒绝（F）；null 可以被拒绝或返回有效非空回复，不能返回 5xx（E）。 | 默认运行 |
| 09_05 | [`test_09_05_completion_length_truncation`](../m2_her_text_tests.py#L524) | [S：必须成功](../README.md#verdict-rules) | 让助手续写长文，给 8 个输出 token。如果自然结束，再换一个续写提示，只给 1 个 token。 | 任一次报告 length 且计数恰好用完额度即可通过。两次有效回答都提前结束记 SKIP；响应损坏、用量缺失或超额立即失败。 | 默认运行 |

## 10 response_usage — 响应结构与 usage

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 10_01 | [`test_10_01_response_envelope`](../m2_her_text_tests.py#L530) | [S：必须成功](../README.md#verdict-rules) | 发送普通问答，读取每份回复的 id、model、created 和 object；流式时还比较同一回复的所有数据包。 | id 和模型名非空，创建时间为正整数，模型名与配置的响应别名一致（未配置时用请求模型名）。完整消息标 chat.completion，增量包标 chat.completion.chunk；同一回复的 id、模型名和时间不能变化。 | 默认运行 |
| 10_02 | [`test_10_02_response_message`](../m2_her_text_tests.py#L538) | [S：必须成功](../README.md#verdict-rules) | 不启用流式，查看第一条候选回复的 message。 | role 应是 assistant，content 应为包含实际文字的字符串。只返回空格会失败。 | 默认运行 |
| 10_03 | [`test_10_03_finish_reason_stop`](../m2_her_text_tests.py#L544) | [S：必须成功](../README.md#verdict-rules) | 用示例让助手简短回答 OK，先给 128 token。若被截断，再放宽到 512 token。 | 任一次有效回答报告 stop 即可，无需逐字回答 OK。若两次都正确用完额度则 SKIP。出现计数时要核对上限，报告 length 却没有对应计数或计数不等于上限则失败。 | 默认运行 |
| 10_04 | [`test_10_04_usage_total_tokens`](../m2_her_text_tests.py#L549) | [S：必须成功](../README.md#verdict-rules) | 把输出额度压低到 1 token，再用 32 token 作另一个变体，读取回复中的 usage。 | 两种额度均须报告正整数 total_tokens。1 token 时正文可空。这个值统计输入加输出，不要求它小于输出额度。 | 默认运行 |
| 10_05 | [`test_10_05_usage_breakdown_math`](../m2_her_text_tests.py#L558) | [S：必须成功](../README.md#verdict-rules) | 发送一条短消息，查看服务对输入、输出和总用量的结算。 | usage 必须存在，total_tokens 是非负整数。输入和输出分项可以一起省略；出现一项就须同时给两项，各为非负整数且相加等于总数。 | 默认运行 |
| 10_06 | [`test_10_06_sensitivity_field_types`](../m2_her_text_tests.py#L572) | [S：必须成功](../README.md#verdict-rules) | 发送普通消息，查找回复上的 input_sensitive、output_sensitive 以及对应的两个 _type 字段。 | 出现的敏感标志须是布尔值，出现的类型须是整数。四项都可省略；日志记录实际见到几项，结果不评价内容审核是否准确。 | 默认运行；字段缺失只记录 |
| 10_07 | [`test_10_07_prompt_tokens_across_modes`](../m2_her_text_tests.py#L586) | [S：必须成功](../README.md#verdict-rules) | 分别用简单对话和七种具名角色对话。每组先发原文，再给末条消息加 256 段背景；流式、非流式各做一遍。OpenAI 流式显式请求 usage。 | 每组四次都需完整计数。在同一种返回方式下，长输入的 prompt_tokens 要比短输入大。只有规则另外指定 prompt_tokens_equal 时才要求两种返回方式的数值相同。 | 需 --run-compat；需返回 prompt_tokens |

## 11 error_codes — 错误处理

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 11_01 | [`test_11_01_invalid_model`](../m2_her_text_tests.py#L636) | [F：必须失败](../README.md#verdict-rules) | 对照请求使用已配置的模型。目标请求依次不发 model，或把它改为不存在的名字、空串、null、数字 42。 | 五种输入都应被拒绝。测试直接发送请求体，省略的 model 不会被客户端补回。 | 默认运行 |
| 11_02 | [`test_11_02_invalid_messages`](../m2_her_text_tests.py#L652) | [F：必须失败](../README.md#verdict-rules) | 正常对话需要消息列表。分别省略 messages、设为 null、字符串 hello 或空对象。 | 四个请求都应被拒绝。若助手照常回答，即使各字段齐全也算失败。 | 默认运行 |
| 11_03 | [`test_11_03_invalid_role`](../m2_her_text_tests.py#L665) | [F：必须失败](../README.md#verdict-rules) | 消息正文都是 Hello，只改变 role：去掉字段、填一个未知名字，或填数字 42。 | 服务应拒绝这三种无有效角色的消息。 | 默认运行 |
| 11_04 | [`test_11_04_invalid_content`](../m2_her_text_tests.py#L686) | [F：必须失败](../README.md#verdict-rules) | 把原生 user 消息的正文依次改成缺失、null、数字、对象，或数组形式的文本、图片、视频、音频样例。 | 八种给定输入都须被拒绝。媒体内容使用占位数据，只能验证这些具体的非字符串写法。 | 默认运行；仅原生接口 |
| 11_05 | [`test_11_05_invalid_name_type`](../m2_her_text_tests.py#L724) | [F：必须失败](../README.md#verdict-rules) | 在一条有效 user 消息上，把说话人名字 name 分别改成数字 42、空对象或空数组。 | 三种非字符串姓名均应被拒绝。与 06_01 中合法地省略 name 分开判断。 | 默认运行 |
| 11_06 | [`test_11_06_authentication_errors`](../m2_her_text_tests.py#L737) | [F：必须失败](../README.md#verdict-rules) | 用正确的 Bearer 凭据确认接口可用后，一次移除 Authorization，另一次改发无效 Bearer 凭据。 | 两个请求都应被拒绝。没有启用 Bearer 鉴权或检测到可能独立授权的额外凭据（例如 Cookie、X-API-Key 或 access_token 查询参数）时跳过，以免把仍已获授权的请求当成异常。 | 默认运行；仅 Bearer 鉴权 |
| 11_07 | [`test_11_07_invalid_request_envelope`](../m2_her_text_tests.py#L771) | [F：必须失败](../README.md#verdict-rules) | 直接发送截断的 JSON、顶层空数组，或在正常请求中把 stream 写成字符串“true”或数字 1。 | 这四种请求均须被拒绝；服务若自动修复输入并正常作答，会使该项失败。 | 默认运行 |
| 11_08 | [`test_11_08_legacy_sample_role_spelling`](../m2_her_text_tests.py#L795) | [F：必须失败](../README.md#verdict-rules) | 在一组能成功的具名示例对话中，只改一个角色名，将 sample_message_user 或 sample_message_ai 改为旧拼写 user_sample_message 或 ai_sample_message。 | 保留内容和名字，正确拼写的对照要先能用，旧拼写应被拒绝。正确拼写本身都失败时记 SKIP。 | 默认运行；仅原生接口；对照请求失败时跳过 |
| 11_09 | [`test_11_09_invalid_message_item`](../m2_her_text_tests.py#L812) | [F：必须失败](../README.md#verdict-rules) | messages 外层仍是列表，但唯一的元素换成 null、字符串、数字或另一个列表。 | 这四种元素都不能作为一条消息提交。即使外层数组合法，服务仍须拒绝。 | 默认运行 |

## 12 long_context — 长输入与 64K 上下文

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 12_01 | [`test_12_01_long_system`](../m2_her_text_tests.py#L822) | [S：必须成功](../README.md#verdict-rules) | 在 system 消息中写入 500 行背景，在开头、中间、末尾各放一个暗号，用户只请助手简单回应。 | 长 system 能得到正常回复即可。无需找回暗号；此处没有把行数换算成 64K token。 | 需 --run-slow |
| 12_02 | [`test_12_02_long_persona_and_samples`](../m2_her_text_tests.py#L840) | [S：必须成功](../README.md#verdict-rules) | 分别把约 500 行背景放到用户设定 user_system 或示例助手回复 sample_message_ai，后一种还配上示例用户提问。最后发一条真实用户消息。 | 两种放法都应得到正常回复。测试覆盖这两类长消息能否提交，不要求助手复述背景。 | 需 --run-slow |
| 12_03 | [`test_12_03_context_within_64k`](../m2_her_text_tests.py#L861) | [S：必须成功](../README.md#verdict-rules) | 使用自动校准或已记录的样本，取一段接近配置窗口上限（相差不超过 384 token）、且在较小输出额度下仍能放得下的真实对话。自动校准时用 1 token 探测，正式请求通常留 64 token。 | 正式请求必须成功并给齐输入、输出和总 token 数。实际 prompt_tokens 要等于样本记录；缺失或不符都会失败。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |
| 12_04 | [`test_12_04_context_over_64k`](../m2_her_text_tests.py#L879) | [F：必须失败](../README.md#verdict-rules) | 对同一份近窗输入先按窗口内额度发送，确认实测输入数，再把输出额度调大，让输入数和申请额度之和超过窗口；自动校准样本使用 2048。 | 窗口内对照须成功且计数一致。内置规则要求超窗请求被拒绝；可用 --contract 指定接受并提供须保留的答案标记。校准、复测或连接失败都不算证明超窗。 | 需 --run-slow；可用 --context-fixture 提供已测好的长输入 |

## 13 role_combo — 七种角色组合

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 13_01 | [`test_13_01_all_seven_roles`](../m2_her_text_tests.py#L906) | [按变体区分，见校验点](../README.md#verdict-rules) | 同一份对话含助手设定、用户设定、场景、一对示例和真实问答。先给每条消息写名字，再只去掉场景和两条示例消息的名字。 | 全具名版本必须能回答（S）。这一组合中同时缺少三个名字时须拒绝（F）；检查前先用具名版作对照。单独的 group 或 user_system 另有正例。 | 默认运行 |
| 13_02 | [`test_13_02_persona_samples_named_history`](../m2_her_text_tests.py#L917) | [S：必须成功](../README.md#verdict-rules) | 在具名七角色对话中加入两位访客各自的物品编号，要求依次回答助手身份、用户身份、场景、历史暗号及两件物品。 | 六项必须依次是 AI_K72、USER_P38、SCENE_R64、CODE_V59、ITEM_A73、ITEM_B84，以竖线分隔。可带 RESULT: 前缀、分隔处空格或首尾竖线；少答、乱序或附加解释会失败。 | 需 --run-behavior（模型行为，单独统计） |
| 13_03 | [`test_13_03_long_history_small_output`](../m2_her_text_tests.py#L941) | [S：必须成功](../README.md#verdict-rules) | 发送二十轮历史，但只给助手 64 个输出 token。 | 必须报告完整用量，输出数不超过 64；若声称因额度用尽而停止，计数须恰为 64。本项不考问答是否记对历史。 | 默认运行 |
| 13_04 | [`test_13_04_roles_with_sampling`](../m2_her_text_tests.py#L948) | [S：必须成功](../README.md#verdict-rules) | 给含设定、场景、示例和真实历史的七角色对话全部带上名字，同时指定 temperature=0.5 和 top_p=0.95。 | 这种角色与采样参数的组合应能得到正常回复。 | 默认运行 |
| 13_05 | [`test_13_05_one_special_name_omitted`](../m2_her_text_tests.py#L958) | [F：必须失败](../README.md#verdict-rules) | 从一份全具名的七角色对话出发，每次只删除一个名字，分别删用户设定、场景、示例用户或示例助手上的 name，其余消息不动。 | 完整具名版先能成功。四种单独删名的版本都须被拒绝。此规则仅对应这一整套对话，不能由此推断所有消息都必须具名。 | 默认运行 |

## 16 guide_alignment — 官网指南中的写法

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 16_01 | [`test_16_01_guide_role_structures`](../m2_her_text_tests.py#L969) | [按变体区分，见校验点](../README.md#verdict-rules) | 发送指南中的三种对话结构：基础助手问答、领航员和实习生的角色扮演、先给示例再继续聊天。每种分别按原样省略名字或给每条消息命名。 | 基础问答两种都应成功。角色扮演和示例对话均要求具名版成功，原样无名版被拒绝；检查拒绝前先跑同内容的具名对照。 | 默认运行 |
| 16_04 | [`test_16_04_context_recall`](../m2_her_text_tests.py#L985) | [S：必须成功](../README.md#verdict-rules) | 在 800 条背景记录的开头、中间、末尾分别藏一个暗号，让模型一次回答三个。 | 回复中必须同时能找到 BEGIN_P38、MIDDLE_P49、END_P50。标记的顺序和额外文字不影响结果。 | 需 --run-behavior（模型行为，单独统计）；需 --run-slow |

## 17 candidate_count — n 多条回复

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 17_01 | [`test_17_01_n_default_single_choice`](../m2_her_text_tests.py#L1003) | [按变体区分，见校验点](../README.md#verdict-rules) | 做四种请求，一种省略候选条数 n，另三种分别设为 null、0、−1。 | 省略 n 必须成功且只有一条候选（S）。另外三种可拒绝或返回一条有效候选，5xx 失败（E）；接受时还要核对响应标识、模型和时间等外层字段。 | 默认运行；仅原生接口 |
| 17_02 | [`test_17_02_n_candidate_count`](../m2_her_text_tests.py#L1020) | [S：必须成功](../README.md#verdict-rules) | 在非流式调用中分别要求 1 条和 2 条候选回复。 | 候选数要与 n 相符，每条均有正文、结束原因和不同的编号，编号从 0 到 n−1；总用量和外层字段也须合法。两条正文允许相同。 | 默认运行；仅原生接口 |
| 17_03 | [`test_17_03_n_one_stream`](../m2_her_text_tests.py#L1028) | [S：必须成功](../README.md#verdict-rules) | 开启流式返回，并显式指定只要一条候选 n=1。 | 应能拼出一条完整回复。各候选片段的 index 都是 0，同一回复的标识、模型和创建时间一致。 | 默认运行；仅原生接口 |
| 17_04 | [`test_17_04_n_invalid_type`](../m2_her_text_tests.py#L1049) | [F：必须失败](../README.md#verdict-rules) | 把 n 设成 1.5、字符串“2”、true、false、对象、列表或 2 的 63 次方（超出有符号 64 位整数上限）。 | 七种输入都应被拒绝。布尔值不能作为整数 1 或 0 被接受。 | 默认运行；仅原生接口 |
| 17_05 | [`test_17_05_n_stream_conflict`](../m2_her_text_tests.py#L1054) | [F：必须失败](../README.md#verdict-rules) | 先检查普通流式请求可用，再要求非流式返回两条候选。成功后仅把 stream 改成 true，仍要求两条。 | 普通流式对照不通记 SKIP。用例内非流式若拿不到两条完整回复直接 FAIL；只有该步成功且随后流式 n=2 被拒绝，整项才算通过。 | 默认运行；仅原生接口 |
| 17_06 | [`test_17_06_n_tools_conflict`](../m2_her_text_tests.py#L1064) | [F：必须失败](../README.md#verdict-rules) | 普通非流式前测通过后，先不带工具请求两条候选，再用 n=1 带上名为 ping 的工具。两项都成功，才用同一个工具请求两条候选。 | 普通前测不通记 SKIP。不带工具的 n=2 必须返回两条。若 n=1 加工具已被正常拒绝，暂时无法判断两者组合是否冲突，记 SKIP；该对照返回 5xx 或坏包则 FAIL。对照接受后，n=2 加工具必须被拒绝。 | 默认运行，仅原生接口。单候选加工具获接受后才发送目标请求。 |
| 17_07 | [`test_17_07_n_with_roles_and_parameters`](../m2_her_text_tests.py#L1087) | [S：必须成功](../README.md#verdict-rules) | 同一份七角色具名对话请求两条候选，并给 temperature=0.7、top_p=0.95。两次分别用旧字段 max_tokens 或新字段 max_completion_tokens 指定 100。 | 两个版本都须返回两条完整候选，响应外层字段和总用量有效。本项只读取合计用量，不能据此证明每条候选消耗多少 token。 | 默认运行；仅原生接口 |
| 17_08 | [`test_17_08_n_configured_boundary`](../m2_her_text_tests.py#L1110) | [按变体区分，见校验点](../README.md#verdict-rules) | 按配置的候选上限 N 发非流式请求（默认 4）。另一个变体在同样的 N 成功后，再多要一条。 | 上限处必须得到 N 条完整回复，多要一条须被拒绝。若 N 本身就请求失败，本用例直接失败，不能当作超过上限的证据。 | 默认运行；--n-limit 可修改上限值 |

## 18 request_metadata — metadata / user / mask_sensitive_info

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 18_01 | [`test_18_01_request_metadata_valid`](../m2_her_text_tests.py#L1130) | [S：必须成功](../README.md#verdict-rules) | 分别传普通 metadata、键和值各长 255 个 ASCII 字符的 metadata、字符串 user 和两个布尔 mask_sensitive_info 值。边界分支另用 85 个三字节中文字符组成键和值。 | 五个目标请求都必须成功并返回有效的外层字段。附加的 255 字节中文输入只记录按何种方式处理：正常接受或明确拒绝均可，5xx 失败（E）。本项不读取服务端日志或检查脱敏效果。 | 默认运行；仅原生接口 |
| 18_02 | [`test_18_02_request_metadata_invalid_type`](../m2_her_text_tests.py#L1181) | [F：必须失败](../README.md#verdict-rules) | 各自发送三种错误 metadata（字符串、数组、值为数字的对象）、两种错误 user（数字、对象）和两种错误 mask_sensitive_info（字符串、数字）。 | 七种类型错误都须拒绝，包括看起来像布尔值的字符串“true”。 | 默认运行；仅原生接口 |
| 18_03 | [`test_18_03_metadata_length_boundary`](../m2_her_text_tests.py#L1189) | [F：必须失败](../README.md#verdict-rules) | 分别把 metadata 的键或值设为 256 个 ASCII 字符。再对相同字段发送 85 个三字节中文字符加一个 ASCII 字符，共 86 个字符、256 个 UTF-8 字节。 | ASCII 边界是主判定，两种请求均须被拒绝（F）。多字节输入是额外观测，接受或拒绝均可，5xx 失败（E）；不能由此判定所有供应商按 UTF-8 字节计长。 | 默认运行；仅原生接口 |

## 19 language_consistency — 回复语言

| Case ID | 函数名 | 结果规则 | 发给供应商的请求 | 怎样判断结果 | 执行条件 |
|:---:|:---|:---|:---|:---|:---|
| 19_01 | [`test_19_01_reply_follows_user_language`](../m2_her_text_tests.py#L1229) | [S：必须成功](../README.md#verdict-rules) | 用 11 种语言或字形分别问周末怎样放松，覆盖简繁中文、英、日、韩、西、法、德、葡、俄、阿。每种返回方式分别评分。 | 每个变体最多取三份合规回复。两次明确使用提问语言即通过，两次明确错语或夹语即失败；样本用尽仍无法区分则记 SKIP。请求或格式错误立即失败。 | 需 --run-behavior（模型行为，单独统计） |
| 19_04 | [`test_19_04_multiturn_language_retention`](../m2_her_text_tests.py#L1267) | [S：必须成功](../README.md#verdict-rules) | 角色设定使用一种语言，三轮旅行对话历史和最后的雨天提问使用另一种。中、英、日、韩之间共 12 种有方向的组合。 | 目标是延续用户一直使用的语言。每种组合和模式最多三次：两次明确匹配通过，两次明确错语或夹语失败，三次仍无充分证据记 SKIP；请求或格式错误立即失败。 | 需 --run-behavior（模型行为，单独统计） |

---

## 附录：parametrize 展开后的 343 个 items

| 展开因子 | 涉及 case |
|:---|:---|
| `stream(2)` | 01_01 / 01_02 / 01_03 / 01_04 / 01_05 / 02_01 / 02_02 / 02_04 / 02_05 / 03_01 / 03_03 / 03_04 / 04_01 / 04_02 / 04_03 / 05_01 / 05_02 / 05_05 / 06_01 / 06_03 / 06_04 / 07_01 / 07_02 / 07_03 / 07_04 / 07_05 / 07_06 / 08_01 / 09_01 / 09_05 / 10_01 / 10_03 / 10_05 / 10_06 / 12_01 / 12_03 / 12_04 / 13_02 / 13_03 / 13_04 / 16_04 |
| `text(5) × stream(2)` | 01_06 |
| `stream(2) × named(2)` | 05_04 / 13_01 |
| `name(3) × stream(2)` | 06_02 |
| `value(3)` | 08_02 / 11_05 |
| `value(5) × stream(2)` | 08_03 / 08_05 |
| `value(4)` | 08_04 |
| `limit(5) × stream(2)` | 09_02 |
| `value(2) × stream(2)` | 09_03 |
| `value(4) × stream(2)` | 09_04 |
| `单项` | 10_02 / 17_03 / 17_05 / 17_06 |
| `limit(2) × stream(2)` | 10_04 |
| `named(2)` | 10_07 |
| `variant(5) × stream(2)` | 11_01 / 18_01 |
| `variant(4) × stream(2)` | 11_02 / 17_01 |
| `variant(3)` | 11_03 |
| `variant(8)` | 11_04 |
| `variant(2) × stream(2)` | 11_06 / 18_03 |
| `variant(4)` | 11_07 |
| `role,alias(2) × stream(2)` | 11_08 |
| `item(4) × stream(2)` | 11_09 |
| `role(2) × stream(2)` | 12_02 |
| `role(4) × stream(2)` | 13_05 |
| `scenario(3) × stream(2) × named(2)` | 16_01 |
| `n(2)` | 17_02 |
| `value(7) × stream(2)` | 17_04 |
| `token_field(2)` | 17_07 |
| `variant(2)` | 17_08 |
| `field,value(7) × stream(2)` | 18_02 |
| `language(11) × stream(2)` | 19_01 |
| `persona,language(12) × stream(2)` | 19_04 |

同一函数中的多次请求（多轮回传、隔离对照、采样重复）不另算 item，实际请求数见运行日志。

# M2-Her 格式校验 — 独立运行包

[English](README_en.md)

可独立 `pytest` 运行，覆盖 M2-Her 模型原生 `/v1/text/chatcompletion_v2` 接口的格式校验：文本、system 人设、七类角色（system / user_system / group / sample_message_user / sample_message_ai / user / assistant）、示例对话、具名历史、采样与输出预算参数、错误处理、usage、SSE 流式协议、`n` 多候选、附加请求字段和语种一致性。
沿用 M3 套件的模块编号、函数命名和 py/md 一一对应的方式，**collect 后共 112 个 case 函数、509 个 items**（text 449 / stream 11 / compat 49）。

## 期望值以线上实际为准

M2-Her 是较早发布的模型，官网文档与实际接口行为有不少出入。本套件的**所有断言都按官方渠道（MiniMax 原生 `/v1/text/chatcompletion_v2`、模型 `M2-her`）2026-11-05 的实际返回设定**，与文档或通识不一致时以线上为准。第三方供应商接入 M2-Her 后，可以直接用这套 case 校验其接口格式是否与官方一致。

- 期望值集中定义在 [`observed.py`](observed.py)（错误信封、`n` 上限、语种行为）和 [`acceptance_baseline.json`](acceptance_baseline.json)（兼容项）；每个 case 的具体期望见 `docs/` 下的 case 清单。
- **工程类断言精确比对**：HTTP 状态、业务码 `base_resp.status_code`、`status_msg` 原文、错误帧格式（纯 JSON / 同一响应体两个 JSON / 单个 SSE 事件）、参数接受与否、候选数、usage 结构、分包形态。例如省略高级角色 name 时，非流式为 HTTP 200 + `2013「invalid params, 400」`，流式为单个 SSE 事件 `1000「unknown error, 999」`，两者都逐字断言。
- **模型行为与语种类断言通常表现**（`--run-behavior`），不为追求 100% 通过而放宽。已观察到的偶发情况会让单轮失败，属于预期内的随机性：
  - 16_02 偶尔在标记后写满重复内容；
  - 19_02 沿用设定语种的组合偶尔改用用户语种；19_03 / 19_01 偶尔夹一句其他语种；19_05 韩→英约 3/10 仍回韩语；
  - 19_06 默认采样偶尔漂到第三种语言；
  - 15_08 偶尔因模型回复过短、20 次采样累计不足 1000 字符而 SKIP（未验证）。
- 某个行为项在多轮中持续失败，说明线上行为变了，应重新观测并更新 `observed.py` 与 case 清单。

## 目录结构

```
m2_her_format_check/
├── conftest.py                 # pytest 开关 / fixture / 日志路径 (xdist-aware)
├── helpers.py                  # HTTP + SSE 传输、请求记录与全部断言工具
├── exercises.py                # 截断阶梯、上下文自动校准、分包采样等多请求流程
├── scenarios.py                # 确定性的消息构造（七角色、示例对话、长文本）
├── language.py                 # 语种一致性的确定性判定规则（不调用模型）
├── observed.py                 # 官方渠道实测的期望值
├── acceptance_baseline.json    # 兼容项（15_* / 10_07 / 12_04）的内置基线
├── m2_her_text_tests.py        # 文本与角色 449 items（01–13、16–19 模块）
├── m2_her_stream_tests.py      # SSE 流式协议 11 items（14 模块）
├── m2_her_compat_tests.py      # 端点兼容、旧字段、扩展参数与分包 49 items（15 模块）
├── pytest.ini                  # python_files=m2_her_*_tests.py
├── requirements.txt            # httpx + pytest + pytest-xdist + openai
├── logs/                       # 每次运行的 jsonl 日志（运行时自动生成，已 git 排除）
└── docs/                       # case 解释（中/英文双语，与 m2_her_*_tests.py 一一对应）
    ├── m2_her_text_cases.md   / m2_her_text_cases_en.md
    ├── m2_her_stream_cases.md / m2_her_stream_cases_en.md
    └── m2_her_compat_cases.md / m2_her_compat_cases_en.md
```

## 必填环境变量

```bash
export M2_HER_BASE_URL="https://your-endpoint.example.com"   # 服务根地址或以 /v1 结尾的 SDK base，不带 completion 路径
export M2_HER_API_KEY="sk-xxx"
```

## 可选环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `M2_HER_MODEL` | `M2-her` | 请求中的模型 ID，可改为供应商别名 |
| `M2_HER_RESPONSE_MODEL` | 同 `M2_HER_MODEL` | 响应 `model` 字段的期望值；接口返回 canonical 名称时填写 |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`；`openai` → `/v1/chat/completions`（此时只运行 15_* 兼容项） |
| `M2_HER_TIMEOUT` | `120` | 单次请求超时（秒） |
| `M2_HER_EXTRA_HEADERS` | (空) | JSON 串，额外注入请求头，例如 `'{"X-Custom-Header": "value"}'` |
| `M2_HER_QUERY_PARAMS` | (空) | JSON 串，追加到 URL 的查询参数，例如 `'{"GroupId": "your-group-id"}'` |
| `M2_HER_RUN_LOG` | `logs/run_<UTC-ts>.jsonl` | 自定义 jsonl 路径；实际文件名会追加 worker 和进程 ID |

## pytest 开关

| 开关 | 作用 |
|------|------|
| `--run-behavior` | 运行模型行为与语种类 case（197 items，validation_tier=behavior） |
| `--run-compat` | 运行兼容项 15_* 与 10_07 |
| `--run-slow` | 运行长输入与多次采样 case（12_*、14_11、15_08、16_04、19_06） |
| `--contract FILE` | 用 JSON 逐键覆盖 `acceptance_baseline.json` |
| `--context-fixture FILE` | 使用已测量的窗口内/超窗样本，代替 12_03/12_04 的自动校准 |
| `--context-window` | 上下文窗口基线，`64000`（默认）或 `65536` |
| `--n-limit N` | 替换 17_08 的 `n` 上限（默认按观测值 4） |

不加任何开关时运行 documented_api 与 implementation_api 两层（251 items），未选择的项明确 SKIP 并写明原因。

## 运行

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 设环境变量（见上）
export M2_HER_BASE_URL=...
export M2_HER_API_KEY=...

# 3a. 默认格式项（不含行为 / 兼容 / 长输入）
pytest

# 3b. 全部 509 个 items，5 并发
pytest -n 5 --run-behavior --run-compat --run-slow

# 3c. 按文件运行
pytest m2_her_text_tests.py
pytest m2_her_stream_tests.py
pytest m2_her_compat_tests.py --run-compat --run-slow

# 3d. 只跑行为 / 语种类
pytest --run-behavior -m behavior
pytest m2_her_text_tests.py -k '19_' --run-behavior --run-slow

# 3e. 单个 case 复现（zsh 中带方括号的 node id 需加引号）
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

首次核对一个新端点时建议先串行跑默认项，避免鉴权、限流等问题被并发放大。

## 判定说明

- **验证分层**：每个 item 的 junit properties 带 `validation_tier`，分别为 `documented_api`（官网/API 格式，202 项）、`implementation_api`（服务端附加字段如 `n`、`metadata`，59 项）、`behavior`（模型行为与语种，197 项）、`endpoint_contract`（兼容项，51 项）。行为项不计入格式通过率。
- **负向用例先做正常对照**：同端点、模型、鉴权与 stream 模式的正常请求失败时，负向用例 SKIP 并说明未验证，不把环境问题当作“正确拒绝”。缺字段、非法 JSON、无鉴权等用例走原始请求入口，测试代码不会自动补参数。无自动重试。
- **输出预算**：截断 / 自然结束使用有界预算阶梯；出现 `finish_reason=length` 时 `completion_tokens` 必须恰好等于预算，缺少真实计数时明确报告测量前提失败。
- **上下文**：12_03/12_04 每种模式最多 8 次 1-token 探针，按真实 `prompt_tokens` 校准接近 64K 的输入，再提高输出预算触发超窗。`1039` 是 TPM 限流，不算上下文拒绝。
- **流式**：原生流式不要求 `[DONE]`；结尾的完整 message 汇总包与 delta 正文分别校验，不重复拼接；中间包 usage 允许为 0。
- **分包质量（15_08）**：按观测到的分包形态验收——每个响应首包 ≤6 字符、中间包 ≥5 字符、单包 ≤512 字符；M3 的五项分档比例只记录不判定。
- **语种一致性（19_*）**：[`language.py`](language.py) 按 Unicode 文字区段、简繁/中日区分字符集和拉丁语系功能词判定主体语种，不调用模型或第三方检测器。严格项要求回复只用目标语种（拉丁字母外来词除外）；观测为沿用设定语种的组合，断言主体语种。

## 覆盖内置基线

其他端点与官方行为不同、且有明确依据时，可用 `--contract` 按完整规则逐键覆盖 `acceptance_baseline.json`，未覆盖的键继续使用内置值：

```json
{
  "15_03/2049": {
    "source": "实际接口说明或已记录的决策引用",
    "outcome": "success",
    "completion_limit": 2048
  }
}
```

每条规则必须有非空 `source` 和 `outcome`（`success` / `reject` / `error`）；`reject` 需指定 `error_kind`（`parameter` / `model` / `auth` / `context`），`error` 需指定 `status_code`、`status_msg` 与 `framing`。可用的键见 [兼容性 case 清单](docs/m2_her_compat_cases.md) 与内置文件。不要按单次运行结果自动生成通过规则。

## 输出

- **stdout**：pytest 标准输出；`--junitxml` 可保存每项的 `validation_tier`。
- **jsonl 日志**：默认写入 `logs/run_<UTC-ts>_<worker>_<pid>.jsonl`，每个请求保留完整 payload、实际请求头、HTTP 状态与业务响应、原始响应字节（Base64）、原始 SSE 事件、解析结果、trace_id、耗时和异常；**不脱敏**，不要提交。分包、校准、计数等测量记录以 `kind` 区分，统计请求数时只计带 `request_number` 的记录。

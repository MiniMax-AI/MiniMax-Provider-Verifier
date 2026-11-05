# M2-Her 格式校验 — 独立运行包

[English](README_en.md)

可独立 `pytest` 运行，覆盖 M2-Her 模型原生 `/v1/text/chatcompletion_v2` 接口的格式校验：文本、system 人设、七种角色（system / user_system / group / sample_message_user / sample_message_ai / user / assistant）、示例对话、带 name 的多人对话、采样与输出长度参数、错误处理、usage、SSE 流式协议、`n` 多条回复、附加请求字段和回复语言。
沿用 M3 套件的模块编号、函数命名和 py/md 一一对应的方式，**collect 后共 103 个 case 函数、403 个 items**（text 343 / stream 11 / compat 49）。

## 预期值怎么来的

M2-Her 是较早发布的模型，官网文档与实际接口行为有不少出入。本套件的预期值**取自官方渠道（MiniMax 原生 `/v1/text/chatcompletion_v2`、模型 `M2-her`）2026-11-05 的实测结果**，用于校验第三方供应商部署的 M2-Her 是否与官方格式一致。判定分三类：

| 类别 | 判定 | 例子 |
|------|------|------|
| 必须成功 | 请求成功，回复格式正确（字段、类型、usage、SSE 帧等逐项检查） | 七种角色都带 name、合法的 temperature / top_p / max_completion_tokens |
| 必须请求失败 | **HTTP 状态码非 200，或 HTTP 200 但响应中业务码（`base_resp.status_code`）非 0 / 带 `error` 对象**，且没有返回回复内容。**不比对具体的错误码、错误信息和返回形态** | 类型错误、缺字段、鉴权失败、超出 64K、n=5、高级角色省略 name |
| 接受或拒绝都可以 | 文档不允许、但官方接口接受的取值：接受时回复格式须正确，拒绝时按“请求失败”判定；**不能返回 5xx** | temperature=0 / 1.01、top_p=0、max_completion_tokens=0 / -1 / null、n=0 / -1 / null、未声明的参数 |

实测的错误场景均返回 HTTP 200，错误写在业务码里，且部分错误码、错误信息并不规范，因此报错类用例按“请求失败”判定，不要求供应商照搬错误码或文案。

错误响应可以使用 JSON、SSE 或多个连续的完整 JSON 对象；解析必须完整，损坏的 UTF-8、JSON 尾部垃圾、不完整或损坏的 SSE 事件都会失败。非 200 的纯文本或 HTML 错误页也可表示拒绝；声明为 JSON / SSE 或以 JSON 对象、数组开头的响应必须正确解析。

模型行为类用例（`--run-behavior`）只保留核心能力，且对官方接口 10 轮全量执行均稳定通过；其中 19_01（用提问的语言回复）每个语种最多请求 3 次、至少 2 次符合即通过。

预期值集中在 [`observed.py`](observed.py)（n 的上限）、[`acceptance_baseline.json`](acceptance_baseline.json)（兼容项）和各测试函数中；每个 case 的预期见 `docs/` 下的 case 清单。

## 目录结构

```
m2_her_format_check/
├── conftest.py                 # pytest 开关 / fixture / 日志路径 (xdist-aware)
├── helpers.py                  # HTTP + SSE 传输、jsonl 日志与全部断言工具
├── exercises.py                # 截断阶梯、上下文自动校准、分包采样等多请求流程
├── scenarios.py                # 确定性的消息构造（七种角色、示例对话、长文本）
├── language.py                 # 回复语言的确定性判定规则（不调用模型）
├── observed.py                 # 官方接口实测得到的取值（n 的上限）
├── acceptance_baseline.json    # 兼容项（15_* / 10_07 / 12_04）的内置预期值
├── m2_her_text_tests.py        # 文本与角色 343 items（01–13、16–19 模块）
├── m2_her_stream_tests.py      # SSE 流式协议 11 items（14 模块）
├── m2_her_compat_tests.py      # 调用方式、旧参数、额外参数与分包 49 items（15 模块）
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
export M2_HER_BASE_URL="https://your-endpoint.example.com"   # API 根地址（或以 /v1 结尾），不带 completion 路径
export M2_HER_API_KEY="sk-xxx"
```

请求地址、请求头和请求体中的 `model` 都来自环境变量，用例代码里没有写死任何地址、密钥或路由信息：

- URL = `M2_HER_BASE_URL` + `/v1/text/chatcompletion_v2`（`M2_HER_API_STYLE=openai` 时为 `/v1/chat/completions`）+ `M2_HER_QUERY_PARAMS`
- 请求头 = `Content-Type` + `M2_HER_EXTRA_HEADERS`；`M2_HER_AUTH_TYPE=bearer` 时再设置 `Authorization: Bearer $M2_HER_API_KEY`
- 请求体 `model` = `M2_HER_MODEL`

## 可选环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `M2_HER_MODEL` | `M2-her` | 请求中的模型 ID，可改为供应商的模型名 |
| `M2_HER_RESPONSE_MODEL` | 同 `M2_HER_MODEL` | 响应 `model` 字段的期望值；接口返回的名称与请求不同时填写 |
| `M2_HER_AUTH_TYPE` | `bearer` | `none` 时不自动添加 Bearer 鉴权（鉴权用例 11_06 跳过）；`M2_HER_EXTRA_HEADERS` 中显式配置的鉴权头仍会发送，包括自定义 `Authorization`。HTTP 与 SDK 使用相同规则 |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`；`openai` → `/v1/chat/completions`（此时只运行 15_* 兼容项） |
| `M2_HER_TIMEOUT` | `120` | 单次请求超时（秒） |
| `M2_HER_EXTRA_HEADERS` | (空) | JSON 串，额外注入请求头，例如 `'{"X-Custom-Header": "value"}'` |
| `M2_HER_QUERY_PARAMS` | (空) | JSON 串，追加到 URL 的查询参数，例如 `'{"GroupId": "your-group-id"}'` |
| `M2_HER_RUN_LOG` | `logs/run_<UTC-ts>.jsonl` | 自定义 jsonl 路径；xdist 并发时每个 worker 追加 `_gw<N>` 后缀 |

## pytest 开关

| 开关 | 作用 |
|------|------|
| `--run-behavior` | 运行模型行为类 case（91 items，validation_tier=behavior） |
| `--run-compat` | 运行兼容项 15_* 与 10_07 |
| `--run-slow` | 运行长输入与多次请求的 case（12_*、14_11、15_08、16_04） |
| `--contract FILE` | 用 JSON 逐条替换 `acceptance_baseline.json` 中的预期值 |
| `--context-fixture FILE` | 提供已测好的窗口内/超窗长输入，代替 12_03/12_04 的自动校准 |
| `--context-window` | 上下文窗口，`64000`（默认）或 `65536` |
| `--n-limit N` | 修改 17_08 使用的 `n` 上限（默认为官方的 4） |

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

# 3b. 全部 403 个 items，5 并发
pytest -n 5 --run-behavior --run-compat --run-slow

# 3c. 按文件运行
pytest m2_her_text_tests.py
pytest m2_her_stream_tests.py
pytest m2_her_compat_tests.py --run-compat --run-slow

# 3d. 只跑模型行为类
pytest --run-behavior -m behavior

# 3e. 单个 case 复现（zsh 中带方括号的 node id 需加引号）
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

首次核对一个新端点时建议先串行跑默认项，避免鉴权、限流等问题被并发放大。

## 判定说明

- **验证分层**：每个 item 的 junit properties 带 `validation_tier`，分别为 `documented_api`（官网/API 格式，202 项）、`implementation_api`（服务端附加字段如 `n`、`metadata`，59 项）、`behavior`（模型行为，91 项）、`endpoint_contract`（兼容项，51 项）。
- **先做正常对照**：“请求失败”和“接受或拒绝都可以”的用例，先发一个同端点、同模型、同鉴权、同流式模式的正常请求；对照失败时该用例 SKIP 并说明未验证，不把服务故障当成“正确拒绝”。缺字段、非法 JSON、无鉴权等用例走原始请求，测试代码不会自动补参数。无自动重试。
- **输出长度**：截断 / 正常结束使用有上限的重试阶梯；出现 `finish_reason=length` 时 `completion_tokens` 必须恰好等于上限，缺少真实计数时明确报告无法验证。
- **上下文**：12_03/12_04 每种模式最多 8 次 1-token 探针，按真实 `prompt_tokens` 拼出接近 64K 的输入，再提高输出上限使其超窗。
- **流式**：原生流式不要求 `[DONE]`；结尾的完整消息汇总包与 delta 正文分别校验；中间包 usage 允许为 0。
- **分包大小（15_08）**：每个响应首包 ≤6 字符、中间包 ≥5 字符、单包 ≤512 字符；M3 的五项分档比例只记录不判定。
- **回复语言（19_*）**：[`language.py`](language.py) 按 Unicode 文字区段、简繁 / 中日区分字符集和拉丁语系功能词判定，不调用模型或第三方检测器；回复只能使用目标语言（拉丁字母外来词除外）。

## 替换内置预期值

其他端点与官方行为不同、且有明确依据时，可用 `--contract` 逐条替换 `acceptance_baseline.json` 中的规则，未替换的规则继续使用内置值：

```json
{
  "15_03/2049": {
    "source": "供应商接口文档或已记录的决策",
    "outcome": "success",
    "completion_limit": 2048
  }
}
```

每条规则必须有非空 `source` 和 `outcome`：`success`（必须成功）、`reject`（必须请求失败）、`either`（接受或拒绝都可以）。可用的键见 [兼容性 case 清单](docs/m2_her_compat_cases.md) 与内置文件。不要按单次运行结果自动生成通过规则。

## 输出

- **stdout**：pytest 标准输出，开头打印 jsonl 路径，如 `[m2_her_api_test] run log → .../logs/run_20261105T120000Z.jsonl`；`--junitxml` 可保存每项的 `validation_tier`。
- **jsonl 日志**：与 M3 套件相同的机制（`helpers.RUN_LOG_PATH` + `_write_log_line`），默认写入 `logs/run_<UTC-ts>.jsonl`，xdist 并发时为 `run_<UTC-ts>_gw<N>.jsonl`。每行一条请求记录：`ts`、`case_id`、`endpoint`、`url`、`model`、`stream`、`elapsed_ms`、`status`、`trace_id`、`request`、`request_headers`（Authorization 只保留首尾字符）、`response`（含原始响应字节与 SSE 事件），以及异常信息；分包、校准等测量记录以 `kind` 区分，统计请求数时只计带 `request_number` 的记录。日志含真实响应，不要提交。

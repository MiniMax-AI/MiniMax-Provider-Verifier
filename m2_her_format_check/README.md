# M2-Her 格式校验 — 独立运行包

[English](README_en.md)

可独立 `pytest` 运行，覆盖 M2-Her 模型原生 `/v1/text/chatcompletion_v2` 接口的格式校验：文本、system 人设、七种角色（system / user_system / group / sample_message_user / sample_message_ai / user / assistant）、示例对话、带 name 的多人对话、采样与输出长度参数、错误处理、usage、SSE 流式协议、`n` 多条回复、附加请求字段和回复语言。
沿用 M3 套件的模块编号、函数命名和 py/md 一一对应的方式，**collect 后共 103 个 case 函数、403 个 items**（text 343 / stream 11 / compat 49）。

## 本轮验证记录

用例与判定修改见 [`f30ce27`](https://github.com/hustc5622/MiniMax-Provider-Verifier/commit/f30ce2704a9ddd4b803af4f544dbf8d73f8593f5)。之后补充了简繁体判定所需的常用字对照：官方端点的连续中文短回复（如“咖啡馆”“当地”）此前没有可区分的字，`19_04` 的 6 个中文用户变体因此记 SKIP。

当前分支收集 103 个函数、403 个供应商测试项，84 项离线回归全部通过。六份中英文清单的 206 行逐项与代码核对。

2026-11-06 在官方 M2-her 原生端点实跑当前分支：

| 配置 | 命令 | 结果 |
|---|---|---|
| 原生，全部开关 | `pytest -n 8 --run-behavior --run-compat --run-slow` | 连续两轮 **403 passed**，无 SKIP |
| 原生，默认 | `pytest -n 8` | 251 passed，152 项因未开启开关跳过 |
| OpenAI 兼容，全部开关 | `M2_HER_API_STYLE=openai pytest -n 8 --run-compat --run-slow --run-behavior` | **49 passed**，其余 354 项不适用该协议 |
| OpenAI 兼容，未加 `--run-compat` | `M2_HER_API_STYLE=openai pytest` | 配置错误，退出码 4 |

运行日志中未出现所用的密钥或查询参数值。

## 预期值怎么来的

M2-Her 是较早发布的模型，官网文档与实际接口行为有不少出入。本套件的预期值**取自官方渠道（MiniMax 原生 `/v1/text/chatcompletion_v2`、模型 `M2-her`）2026-11-05 的实测结果（OpenAI 流式 usage 于 2026-11-06 补测）**，用于校验第三方供应商部署的 M2-Her 是否与官方格式一致。判定分三类：

| 类别 | 判定 | 例子 |
|------|------|------|
| 必须成功 | 请求成功，回复格式正确（字段、类型、usage、SSE 帧等逐项检查） | 七种角色都带 name、合法的 temperature / top_p / max_completion_tokens |
| 必须请求失败 | **HTTP 状态码非 200，或 HTTP 200 但响应中业务码（`base_resp.status_code`）非 0 / 带 `error` 对象**，且没有返回回复内容。**不比对具体的错误码、错误信息和返回形态** | 类型错误、缺字段、鉴权失败、超出 64K、n=5、指定角色组合省略 name |
| 接受或拒绝都可以 | 文档不允许、但官方接口接受的取值：接受时回复格式须正确，拒绝时按“请求失败”判定；**不能返回 5xx** | temperature=0 / 1.01、top_p=0、max_completion_tokens=0 / -1 / null、n=0 / -1 / null、未声明的参数 |

实测的错误场景均返回 HTTP 200，错误写在业务码里，且部分错误码、错误信息并不规范，因此报错类用例按“请求失败”判定，不要求供应商照搬错误码或文案。

错误响应可以使用 JSON、SSE 或多个连续的完整 JSON 对象；解析必须完整，损坏的 UTF-8、JSON 尾部垃圾、不完整或损坏的 SSE 事件都会失败。非 200 的纯文本或 HTML 错误页也可表示拒绝；声明为 JSON / SSE 或以 JSON 对象、数组开头的响应必须正确解析。

模型行为用例通过 `--run-behavior` 单独开启。此前官方端点的十轮记录对应旧版提示与判分器。当前提交对两项语言用例都最多采样三次，详细投票规则见下文。

预期值集中在 [`observed.py`](observed.py)（n 的上限）、[`acceptance_baseline.json`](acceptance_baseline.json)（兼容项）和各测试函数中；每个 case 的预期见 `docs/` 下的 case 清单。

<a id="verdict-rules"></a>

## 统一判定规则（每个 case 都引用）

用例表的 S / F / E 是**目标请求的结果要求**，不是测试结果。目标请求失败，只有符合该 case 的 F/E 规则才会使测试 PASS；正常对照成功本身不算完成测试。表中写的是内置基线，`--contract` 会整条替换指定规则。

| 规则 | 测试通过的条件 | 不能通过的情况 |
|---|---|---|
| **S：必须成功** | HTTP 200，响应可完整解析，正常回复通过本项格式与内容断言 | HTTP 非 200、业务错误、损坏响应、字段或内容断言不符 |
| **F：必须失败** | 已获得 HTTP 响应；HTTP 非 200，或 HTTP 200 中出现整数且非零的 `base_resp.status_code` / 字典类型的 `error`（空对象也算）；并且没有非空白的 `choices[].message.content` / `delta.content` | HTTP 200 正常回复；只有空流、`[DONE]` 或空成功包而没有错误标记；字符串/布尔业务码或非对象 error 不能充当 HTTP 200 的错误标记；已返回正文再报错；声明为 JSON/SSE 的响应损坏 |
| **E：成功或失败均可，禁止 5xx** | 先排除 HTTP 5xx，再按 S 或 F 检查；额外规则仍按该行执行 | 任意 HTTP 5xx、无错误标记的空响应、成功分支格式错误、失败分支格式损坏 |

**HTTP 状态边界：** F 按已确认的“HTTP 非 200”规则处理，所以 3xx、4xx（包括 429）、5xx 都可满足状态条件；E 中 5xx 一律 FAIL。这里证明请求失败，不保证失败原因一定是被修改的字段。正常对照减少端点整体不可用导致的误判，但不能排除之后才发生的故障。连接失败、超时等未取得可判定响应的异常不算“请求失败”通过条件；目标请求发生这些异常会报错。

**错误响应的解析：** JSON 可以是单个对象或多个连续的完整对象；SSE 的事件必须完整且 data 可解析。损坏 UTF-8、NaN/Infinity/-Infinity、JSON 尾部垃圾、坏事件、未结束事件都不能通过。非 200 的纯文本/HTML 错误页允许表示拒绝；声明为 JSON/SSE 或正文以 JSON 对象/数组开头时必须按对应格式解析。错误码、错误文案及 JSON/SSE 封装不要求与官方完全相同。

**成功分支的公共检查：** 非流式默认一条回复；n 用例按指定条数检查 index、message.role/content、finish_reason 和 usage。流式检查 SSE、delta 字段类型、拼接内容、唯一结束原因，以及结束后没有新增正文；汇总包出现时必须与拼接内容相同。默认正文非空；`09_03` 的非正输出预算允许空正文，输出预算检查仅在上限为 1 时允许空正文。流式 usage 是否必须出现、外层 id/model/created 是否核对，由具体 case 明确；不能把“格式正确”理解为每个 case 都检查所有可选字段。

**怎样读 SKIP 和退出码**

- F/E 通常先在同一端点、模型、鉴权和流式模式下发送正常消息。每个 worker 复用对应的对照结果。前测失败时，该项记 SKIP，不能据此认定供应商正确拒绝了请求。
- 用例内另设的正对照必须成功。例如 `12_04` 先用同一份近窗输入核实 token 数，`17_05/06/08` 先证明正常候选数可用。若供应商明确拒绝单候选携带 tools，则 `17_06` 无法判断组合冲突，记 SKIP。
- 协议不适用、缺少指定开关、采样耗尽仍未观察到结束原因或输出上限、语言证据不足、emoji 或分包样本不足，均有各自的 SKIP 原因。已经出现的格式、计数或分包错误仍然失败。
- 实际验收命令缺少端点或必要凭据，或 OpenAI 模式没有指定 `--run-compat`，会报配置错误并以 4 退出。如果整次验收只产生 SKIP，也会非零退出（5）。`--collect-only` 和显式运行离线回归无需凭据。

**name 的适用范围：** 缺 name 的固定失败规则只用于 `05_04`、`13_01`、`13_05`、`16_01` 中列出的具体组合。`03_01` 单独 user_system、`04_01` 单独 group 和 `06_01` 普通 user 等不带 name 的输入仍要求成功，不能泛化为“所有高级角色都必须有 name”。

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
| `M2_HER_AUTH_TYPE` | `bearer` | `none` 时不自动添加 Bearer 鉴权（鉴权用例 11_06 跳过）；`M2_HER_EXTRA_HEADERS` 中显式配置的鉴权头仍会发送，包括自定义 `Authorization`。HTTP 与 SDK 使用相同规则。同时配置 Bearer 与其他可识别凭据时，11_06 也跳过，因为无法隔离 Bearer 的效果 |
| `M2_HER_API_STYLE` | `native` | `native` → `/v1/text/chatcompletion_v2`；`openai` → `/v1/chat/completions`（此时运行 15_* 和 10_07 兼容项） |
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

原生模式不加开关时选择 251 项。OpenAI 模式需传 `--run-compat`，常规兼容项有 47 项，再传 `--run-slow` 可测全部 49 项。两种 OpenAI 调用方式都使用供应商配置的兼容路径。

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

# 只测提供 OpenAI 兼容接口的供应商
M2_HER_API_STYLE=openai pytest --run-compat --run-slow

# 离线验证校验器本身
pytest verifier_regressions/test_*.py

# 3d. 只跑模型行为类
pytest --run-behavior -m behavior

# 3e. 单个 case 复现（zsh 中带方括号的 node id 需加引号）
pytest -v 'm2_her_text_tests.py::TestCombinations::test_13_01_all_seven_roles[non_stream-all_named]'
```

首次核对一个新端点时建议先串行跑默认项，避免鉴权、限流等问题被并发放大。

## 判定说明

- **验证分层**：每个 item 的 junit properties 带 `validation_tier`，分别为 `documented_api`（官网/API 格式，202 项）、`implementation_api`（服务端附加字段如 `n`、`metadata`，59 项）、`behavior`（模型行为，91 项）、`endpoint_contract`（兼容项，51 项）。
- **先做正常对照**：“请求失败”和“接受或拒绝都可以”的用例，先发一个同端点、同模型、同鉴权、同流式模式的正常请求；对照失败时该用例 SKIP 并说明未验证，不把服务故障当成“正确拒绝”。缺字段、非法 JSON、无鉴权等用例走原始请求，测试代码不会自动补参数。无自动重试。
- **输出长度**。先用最多两种提示或预算触发自然结束和截断。兼容项的输出上限最多用三个续写提示。合规回复始终没有触及目标时记 SKIP。已截断时，生成 token 数必须恰好等于上限；必要的计数缺失或矛盾均失败。
- **上下文**。自动校准每种模式最多用 8 次探针。使用外部文件时，窗口内外须共用合法的同一组消息、相同的实测输入 token 数，且输入距 64K 边界不超过 384 token。单跑超窗用例也会先复测这份输入，再提高预留输出。
- **流式**。原生接口不强制提供 `[DONE]`。每个带 usage 的事件都检查字段类型和计数，中间包允许为零。`14_08` 还要求在结束事件或之后观察到正数最终用量。
- **分包大小（15_08）**：每个响应首包 ≤6 字符、中间包 ≥5 字符、单包 ≤512 字符；M3 的五项分档比例只记录不判定。
- **回复语言（19_01、19_04）**。本地规则检查文字、语言特有字符和常用词。每个变体最多采三次。两次明确匹配为 PASS，两次明确不匹配为 FAIL，其余为 SKIP。任何请求或格式错误都立即失败。单独的模型行为项不参与默认的格式验收。

`18_01/18_03` 对 255/256 个 ASCII 字符保留已有的通过和拒绝要求。另发同字节数的多字节输入，记录供应商接受或拒绝；既有 ASCII 实测不能单独确定供应商按字节还是按字符计数。

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
- **JSONL 日志**与 M3 一样，每个 worker 单独写文件。请求记录含 case ID、请求序号、协议、路径、模型、状态及响应证据。URL 去掉用户信息和查询串。请求和响应头仅保留 Accept、Content-Type、Content-Length 的值，其他值遮蔽。若证据中出现配置的私有值，则省略该条正文及其原始编码副本。分包和校准等测量记录有独立的 kind 字段。日志仍含真实模型输入和输出。

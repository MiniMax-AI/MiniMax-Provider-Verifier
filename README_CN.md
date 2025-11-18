# MiniMax-Provider-Verifier

[English](README.md) | [中文](README_CN.md)

**MiniMax-Provider-Verifier** 提供了一个严格、中立的验证方法，旨在评估第三方部署的 MiniMax M2 模型的正确性与可靠性。自 M2 开源以来，大量用户将其集成至生产环境。为了确保广大用户能够持续获得高效、高质量的体验，并践行我们 "Intelligence with Everyone" 的愿景，本工具包提供了一套客观且可复用的标准，用于验证模型部署是否符合预期行为。

## 评估指标

我们从工具调用（Tool Calling）、模式正确性及配置稳定性（如 top-k 设置）等多个维度对供应商的部署进行评估。

主要指标包括：

* **请求成功率（Query-Success-Rate）：** 衡量在允许最多 `max_retry=10` 次尝试的情况下，供应商最终成功返回有效响应的概率。
  - `query_success_rate = successful_query_count / total_query_count`

* **工具调用率（Finish-ToolCalls-Rate）：** 模型触发工具调用的比例（不考量参数正确性，仅考量是否触发）。
  - `finish_tool_calls_rate = finish_tool_calls_count / total_query_count`

* **工具调用触发相似度（ToolCalls-Trigger Similarity）：**  使用 F1 Score 衡量供应商模型与官方参考模型在“是否触发工具”这一行为上的一致性。引用了 K2-Vendor-Verifier 中使用的方法，用于检测部署正确性。参考：[MoonshotAI/K2-Vendor-Verifier](https://github.com/MoonshotAI/K2-Vendor-Verifier)。

  - 定义 `TP = count(供应商触发 AND 官方触发)`, `FP = count(供应商触发 AND 官方未触发)`, `FN = count(供应商未触发 AND 官方触发)`

  - `Precision = TP / (TP + FP)`, `Recall = TP / (TP + FN)`

  - `F1 = 2 · Precision · Recall / (Precision + Recall)`


* **工具调用准确率（ToolCalls-Accuracy）：** 在触发工具调用的前提下，生成的函数名和参数符合预期模式的比例。
  - `accuracy = tool_calls_successful_count / tool_calls_finish_tool_calls`

* **响应有效率（Response-Success-Rate Not Only Reasoning）：** 检测模型是否陷入“仅输出推理过程（Chain-of-Thought）但无有效内容或工具调用”的错误模式。此类模式通常意味着部署存在问题。
  - `Response-success-rate = response_not_only_reasoning_count / only_reasoning_checked_count`

* **语言遵循成功率（Language-Following-Success-Rate）：** 在小语种场景下，检查模型是否能正确遵循语言指令。该指标对 top-k 等解码参数非常敏感。
  - `language_following_success-rate = language_following_valid_count / language_following_checked_count`

## 评估结果

基于我们发布的初始测试集，以下是各供应商的评估结果（每个供应商执行 10 次取平均值）。其中 `minimax` 代表[官方 MiniMax 开放平台](https://platform.minimaxi.com/)的部署表现，作为基准参考。

| 指标 | 请求成功率 | 工具调用率 | 工具调用触发相似度 | 工具调用准确率 | 响应有效率 | 语言遵循成功率 |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax | 100% | 82% | - | 98.54% | 100% | 40% |
| minimax-vllm | 100% | 82.1% | 99.39% | 97.93% | 100% | 50% |
| minimax-sglang | 100% | 82.2% | 99.39% | 98.42% | 100% | - |
| openrouter-atlas-cloud | 90.7% | 76.6% | 98.78% | 98.83% | 99.7% | 50% |
| openrouter-fireworks | 96.37% | 77.4% | 98.78% | 98.19% | 98.4% | 50% |
| openrouter-minimax | 97.36% | 77.9% | 98.78% | 98.59% | 99.6% | - |
| openrouter-siliconflow | 85.59% | 62.9% | 93.67% | 93.8% | 93.4% | 40% |

## 参考阈值

基于当前的评估集，我们提供以下参考阈值来解释供应商性能。符合这些阈值通常意味着部署配置正确且运行稳定：

* **请求成功率** (使用 **max_retry=10**):
应为 **100%**，表明模型可以在合理的重试预算内稳定返回结果。

* **完成工具调用率**:
应 **≈80%**，基于当前评估集，在内部重复测试中，波动幅度通常在 ±2.5% 以内。

* **工具调用触发相似度**:
应 **≥98%**，对官方渠道进行 10 次重复测试后观察到最小相似度为 98.2%。因此，98% 是一个合理的下限。

* **工具调用准确率**:
应 **≥98%**，反映格式标准且符合模式的工具调用。

* **响应有效率**:
应为 **100%**，任何"仅推理"输出（无最终答案或工具调用）的出现都显著表明部署存在异常。

* **语言遵循成功率**:
应 **≥40%**，基于内部多次评估结果，低于此阈值表明潜在的解码问题，在小语种场景尤为明显。

## 快速开始

使用 `verify.py` 脚本即可针对 JSONL 测试集运行验证管道。脚本支持并发请求，并会自动输出详细日志及摘要。

### 示例

```bash
python verify.py sample.jsonl \
  --model minimax/minimax-m2 \
  --base-url https://YOUR_BASE_URL/v1 \
  --api-key YOUR_API_KEY \
  --concurrency 5
```

### 参数说明

- `sample.jsonl`: JSONL 测试集的路径。
- `--model` (必需): 评估模型名称。示例：`minimax/minimax-m2`。
- `--base-url` (必需): 供应商的 API base url。示例：`https://YOUR_BASE_URL/v1`。
- `--api-key` (可选): 认证令牌；或者在环境中设置 `OPENAI_API_KEY`。
- `--concurrency` (可选，整数，默认值=5): 最大并发请求数。
- `--output` (可选，默认值=results.jsonl): 写入详细的每个输入结果的文件。
- `--summary` (可选，默认值=summary.json): 写入从结果计算的统计指标的文件。
- `--timeout` (可选，整数，默认值=600): 每个请求的超时时间（秒）。
- `--retries` (可选，整数，默认值=3): 每个请求的最大自动重试次数。
- `--extra-body` (可选，JSON 字符串): 要合并到每个请求中的额外字段（例如解码参数）。
- `--incremental` (标志): 仅重新运行之前失败或新的请求，与现有输出合并，重新统计结果。

## 后续计划

- [ ] 扩展和完善评估集。
- [ ] 跟踪和测试更多供应商。

## 致谢

ToolCalls-Trigger Similarity 指标的定义方式借鉴自 K2-Vendor-Verifier 框架，并与其保持一致。参见：[MoonshotAI/K2-Vendor-Verifier](https://github.com/MoonshotAI/K2-Vendor-Verifier)。


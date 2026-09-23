# MiniMax-Provider-Verifier

[English](README.md) | [中文](README_CN.md)

**MiniMax-Provider-Verifier** offers a rigorous, vendor-agnostic way to verify whether third-party deployments of the Minimax M2 model are correct and reliable. Since the open-source release of M2, it has been widely adopted and integrated into production services by numerous users. To ensure this vast user base continues to benefit from an efficient, high-quality M2 experience—and to align with our vision of "Intelligence with Everyone"—this toolkit offers an objective, reproducible standard for validating model behavior.

## Evaluation Metrics

We evaluate multiple dimensions of vendor deployments, including tool-calling behavior, schema correctness, and system stability (e.g., detecting potential misconfigurations like incorrect top-k settings).

The primary metrics are:

* **Query-Success-Rate:** Measures the probability that a provider can eventually return a valid response successfully when allowed up to `max_retry=10` attempts.
  - `query_success_rate = successful_query_count / total_query_count`

* **ToolCalls-Match-Rate:** Measures how well the model's "whether to trigger tool-calls" behavior matches the expected labels. Each test case is annotated with `expected_tool_call` (whether a tool call is expected), and this metric calculates the proportion of cases where the actual result matches the expected result.
  - `tool_calls_match_rate = (tool_calls_finish_tool_calls + stop_finish_stop) / expected_tool_call_total_count`
  - Confusion Matrix Statistics:
    - `tool_calls_finish_tool_calls`: expected tool_call, actual tool_call (TP)
    - `tool_calls_finish_stop`: expected tool_call, actual stop (FN)
    - `stop_finish_tool_calls`: expected stop, actual tool_call (FP)
    - `stop_finish_stop`: expected stop, actual stop (TN)

* **ToolCalls-Schema-Accuracy:** Measures the correctness rate of tool-call payloads (e.g., function name and arguments meeting the expected schema) conditional on tool-call being triggered.
  - `schema_accuracy = tool_calls_successful_count / tool_calls_finish_tool_calls`

* **ToolCalls-Trigger Similarity:** Measures the similarity between a third-party deployment's tool-call triggering behavior and the official MiniMax deployment, using the F1 score with the official results as the gold standard.
  - `precision = TP / (TP + FP)`
  - `recall = TP / (TP + FN)`
  - `trigger_similarity = 2 * precision * recall / (precision + recall)`

* **Error-Only-Reasoning-Rate:** Detects a specific error pattern where the model outputs only Chain-of-Thought reasoning without providing valid content or the required tool calls. The presence of this pattern strongly indicates a deployment issue.
  - `error_only_reasoning_rate = error_only_reasoning_count / error_only_reasoning_checked_count`

* **Language-Following-Success-Rate:** Checks whether the model follows language requirements in minor language scenarios; this is sensitive to top-k and related decoding parameters.
  - `language_following_success_rate = language_following_valid_count / language_following_checked_count`

* **Scenario-Check-Pass-Rate:** Validates model behavior in scenario-specific checks, such as whether the model can correctly recall the original parameter order from tool definitions. This metric is sensitive to providers that reorder JSON object keys (e.g., alphabetical sorting of `parameters.properties`), which can degrade the model's schema comprehension.
  - `scenario_check_pass_rate = scenario_check_valid_count / scenario_check_checked_count`

## Evaluation Results

The evaluation results below are computed using our initial release of test prompts, each executed 10 times per provider, with all metrics reported as the mean over the 10-run distribution. As a baseline, `minimax` represents the performance of our [official MiniMax Open Platform](https://platform.minimax.io/ ) deployment, providing a reference point for interpreting other providers' results.

### MiniMax-M3-a Model – September 2026 Data

| Metric | Query-Success-Rate | ToolCalls-Match-Rate | ToolCalls-Schema-Accuracy | Error-Only-Reasoning-Rate | Language-Following-Success-Rate | Scenario-Check-Pass-Rate |
|--------|--------------------|-----------------------------|--------------------|--------------------------------------------|----------------------------------|--------------------------|
| MiniMax-M3-a | 100.00% | 98.70% | 99.64% | 0.00% | 85.00% | 90.00% |

> Baseline results: official MiniMax-M3-a deployment, `pass@10` mean. Result folder: `output-dir/MiniMax-M3-a/`.


### MiniMax-M3 Model – June 2026 Data

| Metric | Query-Success-Rate | ToolCalls-Match-Rate | ToolCalls-Schema-Accuracy | Error-Only-Reasoning-Rate | Language-Following-Success-Rate | Scenario-Check-Pass-Rate |
|--------|--------------------|-----------------------------|--------------------|--------------------------------------------|----------------------------------|--------------------------|
| MiniMax-M3 | 100.00% | 98.80% | 98.93% | 0.00% | 100.00% | 100.00% |


### MiniMax-M2.5/M2.7 Model – May 2026 Data

| Metric | Query-Success-Rate | ToolCalls-Match-Rate | ToolCalls-Schema-Accuracy | Error-Only-Reasoning-Rate | Language-Following-Success-Rate | Scenario-Check-Pass-Rate |
|--------|--------------------|-----------------------------|--------------------|--------------------------------------------|----------------------------------|--------------------------|
| MiniMax-M2.5 | 100% | 98.30% | 98.57% | 0% | 85% | 100% |
| MiniMax-M2.7 | 100% | 98.80% | 99.76% | 0% | 75% | 100% |

### MiniMax-M2.5/M2.7 Model – April 2026 Data (After Metrics Revision)

| Metric | Query-Success-Rate | ToolCalls-Match-Rate | ToolCalls-Schema-Accuracy | Error-Only-Reasoning-Rate | Language-Following-Success-Rate | Scenario-Check-Pass-Rate |
|--------|--------------------|-----------------------------|--------------------|--------------------------------------------|----------------------------------|--------------------------|
| MiniMax-M2.5 | 100% | 99.29% | 95.59% | 0% | 80% | - |
| MiniMax-M2.7 | 100% | 98.50% | 99.64% | 0% | 90% | 90% |

### MiniMax-M2.5 Model – Feb 2026 Data

| Metric | Query-Success-Rate | Finish-ToolCalls-Rate | ToolCalls-Trigger Similarity | ToolCalls-Accuracy | Response Success Rate - Not Only Reasoning | Language-Following-Success-Rate |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax-m2.5 | 100% | 84.75% | - | 97.26% | 100% | 90% |
| openRouter-minimax-fp8 | 100% | 84.55% | 98.98% | 97.25% | 100% | 80% |
| openRouter-minimax-highspeed | 100% | 84.14% | 99.22% | 97.24% | 100% | 80% |
| openRouter-novita-bf16 | 100% | 84.65% | 99.05% | 97.5% | 100% | 70% |
| openRouter-siliconflow/fp8 | 100% | 84.24% | 99.28% | 98.68% | 100% | 80% |
| openRouter-atlas-cloud/fp8 | 100% | 84.75% | 99.10% | 96.18% | 100% | 70% |
| openRouter-fireworks | 96.32% | 81.63% | 98.87% | 96.19% | 100% | 80% |

### MiniMax-M2.1 Model – Jan 2026 Data

| Metric | Query-Success-Rate | Finish-ToolCalls-Rate | ToolCalls-Trigger Similarity | ToolCalls-Accuracy | Response Success Rate - Not Only Reasoning | Language-Following-Success-Rate |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax-m2.1 | 100% | 83.33% | - | 96.61% | 100% | 90.00% |
| minimax-m2.1-vllm(without topk) | 99.90% | 81.84% | 98.78% | 96.42% | 100% | 60.00% |
| minimax-m2.1-vllm | 100% | 82.83% | 98.90% | 93.91% | 100% | 90% |
| minimax-m2.1-sglang | 100% | 83.03% | 99.15% | 95.01% | 100% | 90% |
| infini-ai | 100% | 80.61% | 97.46% | 100% | 100% | 100% |
| openRouter-minimax/fp8 | 100% | 83.23% | 99.03% | 96.11% | 100% | 90% |
| openRouter-minimax/lightning | 99.90% | 83.15% | 98.97% | 96.48% | 100% | 80% |
| openRouter-gmicloud/fp8 | 83.72% | 55.5% | 81.37% | 84.58% | 100% | 70% |
| OpenRouter-novita/fp8 | 99.32% | 83.07% | 99.21% | 96.03% | 100% | 90% |
| fireworks | 100% | 81.1% | 97.77% | 94.29% | 100% | 60% |
| siliconflow | 100% | 82.42% | 98.47% | 96.19% | 100% | 60% |

### MiniMax-M2 Model – Dec 2025 Data

| Metric | Query-Success-Rate | Finish-ToolCalls-Rate | ToolCalls-Trigger Similarity | ToolCalls-Accuracy | Response Success Rate - Not Only Reasoning | Language-Following-Success-Rate |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax | 100% | 83.74% | - | 99.16% | 100% | 90.00% |
| minimax-vllm | 100% | 82.1% | 99.39% | 97.93% | 100% | 50% |
| minimax-sglang | 100% | 82.2% | 99.39% | 98.42% | 100% | - |
| openrouter-atlas-cloud | 90.7% | 76.6% | 98.78% | 98.83% | 99.7% | 50% |
| openrouter-deepinfra | 99.50% | 82.82% | 99.52% | 98.67% | 99.70% | 20.00% |
| openrouter-google-vertex | 100.00% | 82.93% | 99.33% | 98.06% | 99.49% | 40.00% |
| siliconflow | 100.00% | 83.23% | 99.39% | 97.82% | 100.00% | 40.00% |
| fireworks | 100% | 80.2% | 97.72% | 97.86% | 100% | 50% |


## Reference Thresholds

Based on the current evaluation set, we provide the following reference thresholds for interpreting provider performance. These thresholds reflect the expected behavior of a correctly configured and stable deployment:

* **Query-Success-Rate** (with **max_retry=10**):
Should be **100%**, indicating the model can reliably produce a successful response within realistic retry budgets.

* **ToolCalls-Match-Rate**:
Should be **≈98%**, based on repeated internal runs, the match rate consistently hovers around 98% with a fluctuation of approximately ±1%.

* **ToolCalls-Trigger Similarity**:
Should be **≥98%**, we observed a minimum similarity of 98.2% after 10 repeated tests for stable providers. Thus, 98% serves as a reasonable lower bound.

* **ToolCalls-Schema-Accuracy**:
Should be **≥98%**, reflects standard adherence to formatting and schema requirements.

* **Error-Only-Reasoning-Rate**:
Should be **0%**. Any presence of "reasoning-only" output (no final answer or tool-call) strongly signals deployment issues.

* **Language-Following-Success-Rate**:
Should be **≥40%**, based on repeated internal evaluations, values below this threshold indicate potential decoding issues, particularly in minor language scenarios.

* **Scenario-Check-Pass-Rate**:
Should be **100%**. This metric checks whether the provider preserves the original JSON key order in tool definitions. Failures indicate the provider is reordering `parameters.properties` keys (e.g., alphabetical sorting), which can impair model performance on complex nested schemas.

## Get Started

`verify.py` runs the validation pipeline against a JSONL test set (each line is an entire request body), issues requests concurrently, and outputs both detailed results and an aggregated summary.

### Example

```bash
python verify.py sample.jsonl \
  --model minimax/minimax-m2 \
  --base-url https://YOUR_BASE_URL/v1 \
  --api-key YOUR_API_KEY \
  --concurrency 5
```

### Argument Reference

- `sample.jsonl`: Path to the JSONL test set.
- `--model` (required): Evaluation model name. Example: `minimax/minimax-m2`.
- `--base-url` (required): Provider's API endpoint base. Example: `https://YOUR_BASE_URL/v1`.
- `--api-key` (optional): Authentication token; alternatively set `OPENAI_API_KEY` in the environment.
- `--concurrency` (optional, int, default=5): Max concurrent requests.
- `--output` (optional, default=results.jsonl): File to write detailed, per-input results.
- `--summary` (optional, default=summary.json): File to write aggregated metrics computed from results.
- `--timeout` (optional, int, default=600): Per-request timeout in seconds.
- `--retries` (optional, int, default=3): Max automatic retries per request.
- `--extra-body` (optional, JSON string): Extra fields to merge into each request's payload (e.g., decoding parameters).
- `--incremental` (flag): Only rerun previously failed or new requests, merging with existing output; recomputes the summary.

### Batch Testing (Recommended: pass@10)

For comprehensive evaluation with statistical significance, we recommend using the batch verification script which runs multiple iterations and aggregates metrics:

```bash
bash run_batch_sequential.sh \
  --module 'provider-name' \
  --url 'https://api.example.com/v1/' \
  --model 'model-name' \
  --api-key 'your-api-key' \
  --max-workers 10 \
  --mm-model 'MiniMax-M2.5'
```

**Parameters:**

- `--module`: Provider/module name (required)
- `--url`: API endpoint URL (required)
- `--model`: Model name (required)
- `--api-key`: API key (required)
- `--max-workers`: Concurrent request count (default: 10)
- `--stream`: Enable streaming mode
- `--debug`: Debug mode, only run first 10 cases
- `--extra-body`: Extra request body parameters (JSON format)
- `--mm-model`: MiniMax baseline model name for comparison (default: MiniMax-M2.5)

The script will:
1. Execute 10 verification loops (pass@10)
2. Calculate aggregated metrics across all loops
3. Compare results with the baseline model
4. Generate detailed metrics reports in `output-dir/batch_<timestamp>/`

**Output:**
- `metrics_report.json`: Aggregated metrics from all loops
- `comparison_report.json`: Comparison with baseline model
- Individual loop results in `loop_01/`, `loop_02/`, etc.

## Roadmap

- [ ] Expand and refine the evaluation set.
- [ ] Track and test additional providers.

## Acknowledgements

The formulation of the ToolCalls-Trigger Similarity metric is directly derived from and consistent with the definition used in the K2-Vendor-Verifier framework. See: [MoonshotAI/K2-Vendor-Verifier](https://github.com/MoonshotAI/K2-Vendor-Verifier).


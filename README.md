# MiniMax-Provider-Verifier

[English](README.md) | [中文](README_CN.md)

**MiniMax-Provider-Verifier** offers a rigorous, vendor-agnostic way to verify whether third-party deployments of the Minimax M2 model are correct and reliable. Since the open-source release of M2, it has been widely adopted and integrated into production services by numerous users. To ensure this vast user base continues to benefit from an efficient, high-quality M2 experience—and to align with our vision of "Intelligence with Everyone"—this toolkit offers an objective, reproducible standard for validating model behavior.

## Evaluation Metrics

We evaluate multiple dimensions of vendor deployments, including tool-calling behavior, schema correctness, and system stability (e.g., detecting potential misconfigurations like incorrect top-k settings).

The primary metrics are:

* **Query-Success-Rate:** Measures the probability that a provider can eventually return a valid response successfully when allowed up to `max_retry=10` attempts.
  - `query_success_rate = successful_query_count / total_query_count`

* **Finish-ToolCalls-Rate:** Measures the proportion of triggered tool-calls that successfully reach a completed tool-call result, regardless of argument correctness.
  - `finish_tool_calls_rate = finish_tool_calls_count / total_query_count`

* **ToolCalls-Trigger Similarity:** Measures the similarity of "whether to trigger tool-calls" between a provider and a official reference, using the F1 score (harmonic mean of precision and recall). This mirrors the methodology popularized in K2 Vendor Verifier and is used to detect deployment correctness at the decision level. See reference: [MoonshotAI/K2-Vendor-Verifier](https://github.com/MoonshotAI/K2-Vendor-Verifier).

  - Define `TP = count(provider triggers AND official reference triggers)`, `FP = count(provider triggers AND official reference does not)`, `FN = count(provider does not AND official reference triggers)`

  - `Precision = TP / (TP + FP)`, `Recall = TP / (TP + FN)`

  - `F1 = 2 · Precision · Recall / (Precision + Recall)`


* **ToolCalls-Accuracy:** Measures the correctness rate of tool-call payloads (e.g., function name and arguments meeting the expected schema) conditional on tool-call being triggered.
  - `accuracy = tool_calls_successful_count / tool_calls_finish_tool_calls`

* **Response-Success-Rate Not Only Reasoning:** Detects a specific error pattern where the model outputs only Chain-of-Thought reasoning without providing valid content or the required tool calls. The presence of this pattern strongly indicates a deployment issue.
  - `Response-success-rate = response_not_only_reasoning_count / only_reasoning_checked_count`

* **Language-Following-Success-Rate:** Checks whether the model follows language requirements in minor language scenarios; this is sensitive to top-k and related decoding parameters.
  - `language_following_success-rate = language_following_valid_count / language_following_checked_count`

## Evaluation Results

The evaluation results below are computed using our initial release of test prompts, each executed 10 times per provider, with all metrics reported as the mean over the 10-run distribution. As a baseline, `minimax` represents the performance of our [official MiniMax Open Platform](https://platform.minimax.io/ ) deployment, providing a reference point for interpreting other providers' results.


### MiniMax-M2.1 Model – Jan 2026 Data

| Metric | Query-Success-Rate | Finish-ToolCalls-Rate | ToolCalls-Trigger Similarity | ToolCalls-Accuracy | Response Success Rate - Not Only Reasoning | Language-Following-Success-Rate |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax | 100% | 82% | - | 98.54% | 100% | 40% |
| minimax-vllm | 100% | 82.1% | 99.39% | 97.93% | 100% | 50% |
| minimax-sglang | 100% | 82.2% | 99.39% | 98.42% | 100% | - |
| openrouter-atlas-cloud | 90.7% | 76.6% | 98.78% | 98.83% | 99.7% | 50% |
| openrouter-fireworks | 96.37% | 77.4% | 98.78% | 98.19% | 98.4% | 50% |
| openrouter-minimax | 97.36% | 77.9% | 98.78% | 98.59% | 99.6% | - |
| openrouter-siliconflow | 85.59% | 62.9% | 93.67% | 93.8% | 93.4% | 40% |

### MiniMax-M2 Model – Dec 2025 Data

| Metric | Query-Success-Rate | Finish-ToolCalls-Rate | ToolCalls-Trigger Similarity | ToolCalls-Accuracy | Response Success Rate - Not Only Reasoning | Language-Following-Success-Rate |
|--------|--------------------|-----------------------|------------------------------|--------------------|--------------------------------------------|----------------------------------|
| minimax-m2.1 | 100% | 83.33% | - | 96.61% | 100% | 90.00% |
| minimax-m2.1-vllm(without topk) | 99.90% | 81.84% | 98.78% | 96.42% | 100% | 60.00% |
| minimax-m2.1-vllm | 100% | 82.83% | 98.90% | 93.91% | 100% | 90% |
| minimax-m2.1-sglang | 100% | 83.03% | 99.15% | 95.01% | 100% | 90% |
| openRouter-minimax/fp8 | 100% | 83.23% | 99.03% | 96.11% | 100% | 90% |
| openRouter-minimax/lightning | 99.90% | 83.15% | 98.97% | 96.48% | 100% | 80% |
| openRouter-gmicloud/fp8 | 83.72% | 55.5% | 81.37% | 84.58% | 100% | 70% |
| OpenRouter-novita/fp8 | 99.32% | 83.07% | 99.21% | 96.03% | 100% | 90% |
| fireworks | 100% | 81.1% | 97.77% | 94.29% | 100% | 60% |


## Reference Thresholds

Based on the current evaluation set, we provide the following reference thresholds for interpreting provider performance. These thresholds reflect the expected behavior of a correctly configured and stable deployment:

* **Query-Success-Rate** (with **max_retry=10**):
Should be **100%**, indicating the model can reliably produce a successful response within realistic retry budgets.

* **Finish-ToolCalls-Rate**:
Should be **≈80%**, based on repeated internal runs, the trigger rate consistently hovers around 80% with a fluctuation of approximately ±2.5%.

* **ToolCalls-Trigger Similarity**:
Should be **≥98%**, we observed a minimum similarity of 98.2% after 10 repeated tests for stable providers. Thus, 98% serves as a reasonable lower bound.

* **ToolCalls-Accuracy**:
Should be **≥98%**, reflects standard adherence to formatting and schema requirements.

* **Response-Success-Rate Not Only Reasoning**:
Should be **100%**. Any presence of "reasoning-only" output (no final answer or tool-call) strongly signals deployment issues.

* **Language-Following-Success-Rate**:
Should be **≥40%**, based on repeated internal evaluations, values below this threshold indicate potential decoding issues, particularly in minor language scenarios.

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

## Roadmap

- [ ] Expand and refine the evaluation set.
- [ ] Track and test additional providers.

## Acknowledgements

The formulation of the ToolCalls-Trigger Similarity metric is directly derived from and consistent with the definition used in the K2-Vendor-Verifier framework. See: [MoonshotAI/K2-Vendor-Verifier](https://github.com/MoonshotAI/K2-Vendor-Verifier).


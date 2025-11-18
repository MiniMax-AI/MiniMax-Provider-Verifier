import argparse
import asyncio
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Optional

import megfile
from loguru import logger
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm_asyncio

from validator import (
    BaseValidator, 
    ToolCallsValidator, 
    RussianCharactersValidator,
    RepeatNGramValidator,
)


def compute_hash(obj: dict) -> str:
    """Compute a stable hash of the request dict."""
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(s.encode("utf-8")).hexdigest()


# Global validator registry
VALIDATOR_REGISTRY = {
    "tool_calls": ToolCallsValidator,
    "contains_russian_characters_unicode": RussianCharactersValidator,
    "repeat_n_gram": RepeatNGramValidator,
}


class ValidatorRunner:
    """Runner that manages multiple validators and handles request processing."""
    
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: Optional[str] = None,
        concurrency: int = 5,
        output_file: str = "results.jsonl",
        summary_file: str = "summary.json",
        timeout: int = 600,
        max_retries: int = 3,
        extra_body: Optional[dict] = None,
        incremental: bool = False,
        validators: Optional[list[BaseValidator]] = None,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_body = extra_body or {}
        self.output_file = output_file
        self.summary_file = summary_file
        self.incremental = incremental
        
        # Validators management
        # If no validators specified, use default ToolCallsValidator
        self.validators = validators if validators is not None else [ToolCallsValidator()]
        
        self.results: list[dict] = []
        
        # Stability metric: record all request attempts (including retries)
        self.all_request_count = 0
        self._count_lock = asyncio.Lock()

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

        logger.info(f"Initialized with {len(self.validators)} validators: {[v.name for v in self.validators]}")
        logger.info(f"Results will be saved to {self.output_file}")
        logger.info(f"Summary will be saved to {self.summary_file}")
    
    @staticmethod
    def _is_error_only_reasoning_response(response: dict) -> bool:
        """
        Default detection: check if response contains only reasoning, with empty content and tool_calls.
        This check should always be performed regardless of check_type.
        """
        try:
            if not response or "choices" not in response or not response["choices"]:
                return False
            message = response["choices"][0].get("message") or {}
            reasoning = message.get("reasoning") or ""
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls")
            # Compatible with None / [] / non-list cases
            if isinstance(tool_calls, list):
                has_tool_calls = len(tool_calls) > 0
            else:
                has_tool_calls = bool(tool_calls)
            return bool(reasoning) and (not content) and (not has_tool_calls)
        except Exception:
            return False
    
    def add_validator(self, validator: BaseValidator):
        """Add a new validator to the runner."""
        self.validators.append(validator)
        logger.info(f"Added validator: {validator.name}")
    
    def prepare_request(self, request: dict) -> dict:
        """Process request messages and set model."""
        req = request.copy()
        if "messages" in req:
            for message in req["messages"]:
                if message.get("role") == "_input":
                    message["role"] = "system"
        if self.model:
            req["model"] = self.model
        # Remove custom fields, do not pass to API
        req.pop("check_type", None)
        return req

    def read_jsonl(self, file_path: str) -> list[dict]:
        """Load and prepare JSONL requests, compute hash."""
        requests = []
        with megfile.smart_open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    raw_req = json.loads(line.strip())
                    prepared_req = self.prepare_request(raw_req)
                    requests.append(
                        {
                            "data_index": line_num,
                            "raw": raw_req,
                            "prepared": prepared_req,
                            "hash": compute_hash(prepared_req),
                        }
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing line {line_num}: {e}")
        return requests

    def read_result_jsonl(self, file_path: str) -> list[dict]:
        """Read existing results from a JSONL file."""
        results = []
        with megfile.smart_open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                results.append(json.loads(line))
        return results

    async def send_request(self, request: dict) -> tuple[str, dict]:
        """Send a single request to the API with retry logic."""
        last_error = None
        
        for retry_attempt in range(self.max_retries):
            # Record each request attempt (including retries)
            async with self._count_lock:
                self.all_request_count += 1
            
            try:
                if request.get("stream", False):
                    return await self._handle_stream_request(request)
                else:
                    response = await self.client.chat.completions.create(**request, extra_body=self.extra_body)
                    return "success", response.model_dump()
            except Exception as e:
                last_error = e
                if retry_attempt < self.max_retries - 1:
                    # Calculate exponential backoff delay: 2^retry_attempt seconds, max 32 seconds
                    delay = min(2 ** retry_attempt, 32)
                    logger.warning(
                        f"Request failed (attempt {retry_attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay} seconds..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
        
        return "failed", {"error": str(last_error)}

    async def _handle_stream_request(self, request: dict) -> tuple[str, dict]:
        """Handle streaming request."""
        try:
            stream = await self.client.chat.completions.create(**request, extra_body=self.extra_body)

            request_id = None
            created = None
            full_content = []
            tool_calls: dict[int, dict] = {}
            finish_reason = None
            usage = None
            provider = None

            async for event in stream:
                if hasattr(event, 'id') and event.id:
                    request_id = event.id
                if hasattr(event, 'created') and event.created:
                    created = event.created

                if hasattr(event, 'provider') and event.provider:
                    provider = event.provider

                if not hasattr(event, 'choices') or not event.choices:
                    logger.warning("Empty choices in stream event")
                    continue

                choice = event.choices[0]

                if hasattr(choice, 'delta') and choice.delta:
                    if hasattr(choice.delta, 'content') and choice.delta.content:
                        full_content.append(choice.delta.content)

                    if hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
                        for tc in choice.delta.tool_calls:
                            idx = tc.index if tc.index is not None else 0

                            if idx not in tool_calls:
                                tool_calls[idx] = {
                                    "id": tc.id,
                                    "type": tc.type,
                                    "function": {"name": "", "arguments": ""},
                                }

                            if hasattr(tc, 'function') and tc.function:
                                if hasattr(tc.function, 'name') and tc.function.name:
                                    tool_calls[idx]["function"]["name"] = tc.function.name
                                if hasattr(tc.function, 'arguments') and tc.function.arguments:
                                    tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                if hasattr(choice, 'finish_reason') and choice.finish_reason:
                    finish_reason = choice.finish_reason

                if hasattr(choice, 'usage') and choice.usage:
                    usage = choice.usage

            response = {
                "id": request_id,
                "object": "chat.completion",
                "created": created,
                "model": request.get("model", ""),
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "".join(full_content),
                            "tool_calls": (
                                list(tool_calls.values()) if tool_calls else None
                            ),
                        },
                        "finish_reason": finish_reason or "stop",
                    }
                ],
                "usage": usage,
                "provider": provider
            }
            return "success", response
        except Exception as e:
            logger.error(f"Stream request failed: {e}")
            return "failed", {"error": str(e)}

    async def process_request(self, prepared_req: dict, data_index: int) -> dict:
        """Process a single request and run all validators."""
        async with self.semaphore:
            start_time = time.time()
            status, response = await self.send_request(prepared_req["prepared"])
            duration_ms = int((time.time() - start_time) * 1000)

            # Base result
            result = {
                "data_index": data_index,
                "request": prepared_req["prepared"],
                "response": response,
                "status": status,
                "finish_reason": None,
                "last_run_at": datetime.now().isoformat(),
                "duration_ms": duration_ms,
                "hash": prepared_req["hash"],
                "provider": response.get("provider", ''),
            }
            
            # Extract finish_reason and content for backward compatibility
            resp_content = None
            if response and "choices" in response:
                choice = response["choices"][0] if response["choices"] else {}
                result["finish_reason"] = choice.get("finish_reason")
                # Extract content from response
                message = choice.get("message", {})
                resp_content = message.get("content")
            
            # Always perform 'Error Only Reasoning' detection regardless of check_type
            result["error_only_reasoning_checked"] = 1
            result["error_only_reasoning"] = self._is_error_only_reasoning_response(response)
            
            # Determine which validators to use based on check_type
            check_types = prepared_req.get("raw", {}).get("check_type", [])
            validators_to_run = []
            
            if check_types:
                # If check_type is specified, use corresponding validators
                for check_type in check_types:
                    if check_type in VALIDATOR_REGISTRY:
                        validator_class = VALIDATOR_REGISTRY[check_type]
                        # Create validator instance (if it's a class)
                        if isinstance(validator_class, type):
                            validators_to_run.append(validator_class())
                        else:
                            validators_to_run.append(validator_class)
                    else:
                        logger.warning(f"Unknown check_type: {check_type}")
            else:
                # If no check_type specified, use default validator list
                validators_to_run = self.validators
            
            # Run selected validators and merge their results
            for validator in validators_to_run:
                try:
                    validation_result = validator.validate(
                        prepared_req["prepared"], 
                        response, 
                        status,
                        resp_content
                    )
                    result.update(validation_result)
                except Exception as e:
                    logger.error(f"Validator {validator.name} failed: {e}")
            
            return result

    async def validate_file(self, file_path: str):
        """Validate all requests from a file, supports incremental mode."""
        all_requests = self.read_jsonl(file_path)
        existing_results = []
        existing_hash_map = {}

        if self.incremental and megfile.smart_exists(self.output_file):
            existing_results = self.read_result_jsonl(self.output_file)
            for r in existing_results:
                existing_hash_map[r["hash"]] = r
            logger.info(f"Loaded {len(existing_results)} existing results")

        tasks = []
        self.results = []

        for req in all_requests:
            h = req["hash"]
            data_index = req["data_index"]
            if self.incremental and h in existing_hash_map:
                r = existing_hash_map[h]
                if r.get("status") == "success":
                    self.results.append(r)
                    continue  # skip successful
            tasks.append(self.process_request(req, data_index))

        with tqdm_asyncio(total=len(tasks), desc="Processing", unit="req") as pbar:
            for task in asyncio.as_completed(tasks):
                try:
                    res = await task
                    self.results.append(res)
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                finally:
                    pbar.update(1)

        self.results.sort(key=lambda r: r["data_index"])

        # Save results
        with megfile.smart_open(self.output_file, "w", encoding="utf-8") as f:
            for r in self.results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Compute summary
        self.compute_summary()
        with megfile.smart_open(self.summary_file, "w", encoding="utf-8") as f:
            json.dump(self.summary, f, ensure_ascii=False, indent=4)

        logger.info(f"Results saved to {self.output_file}")
        logger.info(f"Summary saved to {self.summary_file}")

    def compute_summary(self):
        """Compute summary from all results using all validators."""
        summary = {
            "model": self.model,
            "success_count": 0,
            "failure_count": 0,
            "all_count": self.all_request_count,
        }
        
        # Basic statistics
        for r in self.results:
            status = r.get("status")
            if status == "success":
                summary["success_count"] += 1
            else:
                summary["failure_count"] += 1
        
        # Collect all validator types that were used
        used_validators = set()
        for r in self.results:
            # Determine which validators were used based on result fields
            if "tool_calls_finish_reason" in r:
                used_validators.add("tool_calls")
            if "language_following_checked" in r:
                used_validators.add("contains_russian_characters_unicode")
            if "error_repeating_checked" in r:
                used_validators.add("repeat_n_gram")
        
        # Compute summary for each used validator
        # Compute summary for each used validator
        for validator_type in used_validators:
            if validator_type in VALIDATOR_REGISTRY:
                validator_class = VALIDATOR_REGISTRY[validator_type]
                # Create validator instance
                # Create validator instance
                if isinstance(validator_class, type):
                    validator = validator_class()
                else:
                    validator = validator_class
                
                try:
                    validator_summary = validator.compute_summary(self.results)
                    summary.update(validator_summary)
                except Exception as e:
                    logger.error(f"Failed to compute summary for validator {validator_type}: {e}")
        
        # Summarize 'Error Only Reasoning' metrics (always checked by default)
        try:
            total_checked = len(self.results)
            error_count = 0
            for r in self.results:
                # Recompute for compatibility with historical results in incremental mode
                if self._is_error_only_reasoning_response(r.get("response")):
                    error_count += 1
            summary["error_only_reasoning_checked_count"] = total_checked
            summary["error_only_reasoning_count"] = error_count
            summary["error_only_reasoning_rate"] = (error_count / total_checked) if total_checked > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to compute summary for error_only_reasoning: {e}")
        
        # Compute stability metric: success rate
        if summary["all_count"] > 0:
            summary["success_rate"] = round(summary["success_count"] / summary["all_count"], 2)
        else:
            summary["success_rate"] = 0.0
        
        self.summary = summary


async def main():
    parser = argparse.ArgumentParser(
        description="Validate LLM tool calls via HTTP API with concurrency and optional incremental re-run.\n\n"
        "Each line in the JSONL test set must be a complete LLM request body, e.g., including messages and optional tools.\n"
        "Project tip: a typical test set file is named `samples.jsonl` in the repo path."
    )

    parser.add_argument(
        "file_path",
        help=(
            "Path to the test set file in JSONL format.\n"
            "Example line in JSONL:\n"
            '  {"messages":[{"role":"system","content":"You are a helpful assistant."},\n'
            '               {"role":"user","content":"Find info about company X"}],\n'
            '   "tools":[{"type":"function","function":{"name":"search","parameters":{"query":"company X"}}}]}\n\n'
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Evaluation model name, e.g., kimi-k2-0905-preview",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="API endpoint, e.g., https://api.moonshot.cn/v1",
    )
    parser.add_argument(
        "--api-key", help="API key for authentication (or set OPENAI_API_KEY in env)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent requests (default: 5)",
    )
    parser.add_argument(
        "--output",
        default="results.jsonl",
        help="Path to save detailed results (default: results.jsonl)",
    )
    parser.add_argument(
        "--summary",
        default="summary.json",
        help="Path to save aggregated summary (default: summary.json)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-request timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=10,
        help="Number of retries on failure (default: 3)",
    )
    parser.add_argument(
        "--extra-body",
        type=str,
        help=(
            "Extra JSON body as string.\n"
        ),
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help=(
            "Incremental mode: only rerun previously failed or new requests, merge results into existing output file.\n"
            "Existing successful results are preserved, summary will be recalculated."
        ),
    )

    args = parser.parse_args()

    extra_body = {}
    if args.extra_body:
        try:
            extra_body = json.loads(args.extra_body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON for --extra-body: {e}")
            return

    # Use ToolCallsValidator by default, can add more validators here
    validators = [ToolCallsValidator()]
    
    runner = ValidatorRunner(
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        concurrency=args.concurrency,
        output_file=args.output,
        summary_file=args.summary,
        timeout=args.timeout,
        max_retries=args.retries,
        extra_body=extra_body,
        incremental=args.incremental,
        validators=validators,
    )
    await runner.validate_file(args.file_path)


if __name__ == "__main__":
    asyncio.run(main())
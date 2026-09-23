#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Batch Metrics Calculation Script
Reads all [provider]_summary.json files in the target folder and calculates key metrics

Usage:
    python3 scripts/calculate_batch_metrics.py --root-dir result4 --provider amazonaws
"""

import os
import sys
import json
import glob
from pathlib import Path
from typing import Dict, List, Optional

# Add scripts directory to Python path for running from project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Import calculate_toolcall_similarity module
from calculate_toolcall_similarity import calculate_tool_call_f1

# Model version -> Reference data folder mapping
REFERENCE_FOLDER_MAP = {
    'M2.5': PROJECT_ROOT / 'MiniMax-M2.5',
    'M2.7': PROJECT_ROOT / 'MiniMax-M2.7',
    'M3':   PROJECT_ROOT / 'MiniMax-M3',
}

# Default sample.jsonl path
DEFAULT_SAMPLE_FILE = PROJECT_ROOT / 'sample.jsonl'


def get_expected_tool_call_count(sample_file: Path = None) -> dict:
    """
    Read sample.jsonl and count expected_tool_call values
    Returns: {'true': count, 'false': count, 'total': count}
    """
    if sample_file is None:
        sample_file = DEFAULT_SAMPLE_FILE
    
    if not sample_file.exists():
        return {'true': 0, 'false': 0, 'total': 0}
    
    true_count = 0
    false_count = 0
    
    with open(sample_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                val = data.get('expected_tool_call')
                if val is True:
                    true_count += 1
                elif val is False:
                    false_count += 1
    
    return {
        'true': true_count,
        'false': false_count,
        'total': true_count + false_count
    }


def detect_model_version(model_name: str) -> Optional[str]:
    """
    Detect MiniMax version from model name, returns 'M2.5' / 'M2.7' / 'M3' or None
    Supports common formats: minimax-m2.5-preview, MiniMax-M2.7, m3, etc.
    """
    if not model_name:
        return None
    name = model_name.lower()
    if 'm3' in name or '3.0' in name:
        return 'M3'
    if 'm2.7' in name or '2.7' in name:
        return 'M2.7'
    if 'm2.5' in name or '2.5' in name:
        return 'M2.5'
    return None


def load_minimax_reference_by_version(version: str) -> Optional[List[Dict]]:
    """
    Auto-locate reference folder by version and load minimax_results.jsonl
    """
    ref_dir = REFERENCE_FOLDER_MAP.get(version)
    if ref_dir is None:
        print(f"Warning: Reference folder not configured for version {version}")
        return None
    if not ref_dir.exists():
        print(f"Warning: Reference folder does not exist: {ref_dir}")
        return None

    pattern = str(ref_dir / '**' / 'minimax_results.jsonl')
    files = glob.glob(pattern, recursive=True)
    if not files:
        print(f"Warning: minimax_results.jsonl not found in {ref_dir}")
        return None

    ref_file = sorted(files)[0]
    print(f"Using {version} reference file: {ref_file}")
    return load_jsonl(ref_file)


def calculate_average_token_usage(token_usage_list: List[Dict]) -> Dict:
    """
    Calculate average of multiple token_usage dictionaries
    
    Args:
        token_usage_list: List of token_usage dictionaries
    
    Returns:
        Averaged token_usage dictionary
    """
    if not token_usage_list:
        return {}
    
    result = {}
    token_types = ['prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'cached_tokens']
    
    for token_type in token_types:
        values = []
        totals = []
        for tu in token_usage_list:
            if token_type in tu:
                values.append(tu[token_type].get('average', 0))
                totals.append(tu[token_type].get('total', 0))
        
        if values:
            result[token_type] = {
                'average': sum(values) / len(values),
                'total': sum(totals),
            }
    
    # Calculate sample count
    samples_with_usage = sum(tu.get('samples_with_usage', 0) for tu in token_usage_list)
    total_samples = sum(tu.get('total_samples', 0) for tu in token_usage_list)
    result['samples_with_usage'] = samples_with_usage
    result['total_samples'] = total_samples
    
    return result


def find_summary_files(root_dir: str, provider: str = None) -> List[str]:
    """
    Recursively find all summary.json files matching naming convention
    Naming convention: *_summary.json or {provider}_summary.json
    
    Args:
        root_dir: Root directory path
        provider: Specified provider name, if provided only find files for that provider
    
    Returns:
        List of all found summary.json file paths
    """
    if provider:
        # If provider specified, only find summary files for that provider
        pattern = os.path.join(root_dir, "**", f"{provider}_summary.json")
    else:
        # Otherwise find all *_summary.json files
        pattern = os.path.join(root_dir, "**", "*_summary.json")
    
    files = glob.glob(pattern, recursive=True)
    return sorted(files)


def load_summary_data(file_path: str) -> Dict:
    """
    Load summary.json file data
    
    Args:
        file_path: File path
    
    Returns:
        JSON data dictionary
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error: Cannot read file {file_path}: {e}")
        return None


def load_jsonl(file_path: str) -> List[Dict]:
    """
    Load JSONL file
    
    Args:
        file_path: File path
    
    Returns:
        Data list
    """
    try:
        data = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        return data
    except Exception as e:
        print(f"Error: Cannot read file {file_path}: {e}")
        return None


def load_minimax_reference(root_dir: str) -> Optional[List[Dict]]:
    """
    Load minimax as reference data
    
    Args:
        root_dir: Root directory path
    
    Returns:
        minimax results data list, None if not found
    """
    # Find minimax_results.jsonl file (supports *minimax*_results.jsonl pattern)
    pattern = os.path.join(root_dir, "**", "*minimax*_results.jsonl")
    files = glob.glob(pattern, recursive=True)
    
    if not files:
        print(f"Warning: minimax_results.jsonl not found, cannot calculate ToolCalls-Trigger Similarity")
        return None
    
    # Use the first found file
    minimax_file = files[0]
    print(f"Using minimax reference file: {minimax_file}")
    
    return load_jsonl(minimax_file)


def calculate_metrics(data: Dict, expected_tool_call_stats: dict = None) -> Dict:
    """
    Calculate metrics based on summary data
    
    Args:
        data: summary.json data dictionary
        expected_tool_call_stats: expected_tool_call statistics from sample.jsonl
                                  {'true': count, 'false': count, 'total': count}
    
    Returns:
        Calculated metrics dictionary
    """
    metrics = {}
    
    # 1. Query-Success-Rate = success_count / all_count
    all_count = data.get('all_count', 0)
    success_count = data.get('success_count', 0)
    metrics['Query-Success-Rate'] = success_count / all_count if all_count > 0 else 0
    
    # 2. ToolCalls-Match-Rate = (tool_calls_finish_tool_calls + stop_finish_stop) / expected_tool_call_total_count
    #    Denominator prioritizes expected_tool_call label count from sample.jsonl
    tool_calls_finish_tool_calls = data.get('tool_calls_finish_tool_calls', 0)
    stop_finish_stop = data.get('stop_finish_stop', 0)
    
    # Denominator priority: 1. External stats  2. Summary stats  3. success_count
    if expected_tool_call_stats and expected_tool_call_stats.get('total', 0) > 0:
        match_rate_denominator = expected_tool_call_stats['total']
    elif data.get('expected_tool_call_total_count', 0) > 0:
        match_rate_denominator = data['expected_tool_call_total_count']
    else:
        match_rate_denominator = success_count
    
    metrics['ToolCalls-Match-Rate'] = (tool_calls_finish_tool_calls + stop_finish_stop) / match_rate_denominator if match_rate_denominator > 0 else 0
    
    # 3. ToolCalls-Schema-Accuracy = tool_calls_successful_count / tool_calls_finish_tool_calls
    tool_calls_successful_count = data.get('tool_calls_successful_count', 0)
    metrics['ToolCalls-Schema-Accuracy'] = tool_calls_successful_count / tool_calls_finish_tool_calls if tool_calls_finish_tool_calls > 0 else 0
    
    # 4. Error-Only-Reasoning-Rate = error_only_reasoning_count / error_only_reasoning_checked_count
    error_only_reasoning_count = data.get('error_only_reasoning_count', 0)
    error_only_reasoning_checked_count = data.get('error_only_reasoning_checked_count', 0)
    metrics['Error-Only-Reasoning-Rate'] = error_only_reasoning_count / error_only_reasoning_checked_count if error_only_reasoning_checked_count > 0 else 0
    
    # 5. Language-Following-Success-Rate = language_following_valid_count / language_following_checked_count
    language_following_valid_count = data.get('language_following_valid_count', 0)
    language_following_checked_count = data.get('language_following_checked_count', 0)
    metrics['Language-Following-Success-Rate'] = language_following_valid_count / language_following_checked_count if language_following_checked_count > 0 else 0

    # 6. Scenario-Check-Pass-Rate = scenario_check_valid_count / scenario_check_checked_count
    scenario_check_valid_count = data.get('scenario_check_valid_count', 0)
    scenario_check_checked_count = data.get('scenario_check_checked_count', 0)
    metrics['Scenario-Check-Pass-Rate'] = scenario_check_valid_count / scenario_check_checked_count if scenario_check_checked_count > 0 else None

    # 7. Token Usage Statistics (if available)
    token_usage = data.get('token_usage', {})
    if token_usage:
        metrics['token_usage'] = {}
        # Extract average values for each token type
        for token_type in ['prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'cached_tokens']:
            if token_type in token_usage:
                metrics['token_usage'][token_type] = {
                    'average': token_usage[token_type].get('average', 0),
                    'total': token_usage[token_type].get('total', 0),
                    'min': token_usage[token_type].get('min', 0),
                    'max': token_usage[token_type].get('max', 0),
                }
        metrics['token_usage']['samples_with_usage'] = token_usage.get('samples_with_usage', 0)
        metrics['token_usage']['total_samples'] = token_usage.get('total_samples', 0)
    
    return metrics


def print_file_metrics(file_path: str, data: Dict, metrics: Dict):
    """
    Print metrics for a single file
    """
    model = data.get('model', 'Unknown')
    print(f"\n{'='*80}")
    print(f"File: {file_path}")
    print(f"Model: {model}")
    print(f"{'-'*80}")
    print(f"Raw Data:")
    print(f"  - Total queries (all_count): {data.get('all_count', 0)}")
    print(f"  - Success count (success_count): {data.get('success_count', 0)}")
    print(f"  - Failure count (failure_count): {data.get('failure_count', 0)}")
    print(f"  - ToolCalls finish count (tool_calls_finish_tool_calls): {data.get('tool_calls_finish_tool_calls', 0)}")
    print(f"  - ToolCalls success count (tool_calls_successful_count): {data.get('tool_calls_successful_count', 0)}")
    print(f"  - Only reasoning error checked (error_only_reasoning_checked_count): {data.get('error_only_reasoning_checked_count', 0)}")
    print(f"  - Only reasoning error count (error_only_reasoning_count): {data.get('error_only_reasoning_count', 0)}")
    print(f"  - Language following checked (language_following_checked_count): {data.get('language_following_checked_count', 0)}")
    print(f"  - Language following valid (language_following_valid_count): {data.get('language_following_valid_count', 0)}")
    print(f"  - Scenario check checked (scenario_check_checked_count): {data.get('scenario_check_checked_count', 0)}")
    print(f"  - Scenario check valid (scenario_check_valid_count): {data.get('scenario_check_valid_count', 0)}")
    print(f"{'-'*80}")
    print(f"Calculated Metrics:")
    print(f"  1. Query-Success-Rate: {metrics['Query-Success-Rate']:.4f} ({metrics['Query-Success-Rate']*100:.2f}%)")
    print(f"  2. ToolCalls-Match-Rate: {metrics['ToolCalls-Match-Rate']:.4f} ({metrics['ToolCalls-Match-Rate']*100:.2f}%)")
    if metrics.get('ToolCalls-Trigger-Similarity') is not None:
        print(f"  3. ToolCalls-Trigger-Similarity: {metrics['ToolCalls-Trigger-Similarity']:.4f} ({metrics['ToolCalls-Trigger-Similarity']*100:.2f}%)")
    print(f"  4. ToolCalls-Schema-Accuracy: {metrics['ToolCalls-Schema-Accuracy']:.4f} ({metrics['ToolCalls-Schema-Accuracy']*100:.2f}%)")
    print(f"  5. Error-Only-Reasoning-Rate: {metrics['Error-Only-Reasoning-Rate']:.4f} ({metrics['Error-Only-Reasoning-Rate']*100:.2f}%)")
    print(f"  6. Language-Following-Success-Rate: {metrics['Language-Following-Success-Rate']:.4f} ({metrics['Language-Following-Success-Rate']*100:.2f}%)")
    if metrics.get('Scenario-Check-Pass-Rate') is not None:
        print(f"  7. Scenario-Check-Pass-Rate: {metrics['Scenario-Check-Pass-Rate']:.4f} ({metrics['Scenario-Check-Pass-Rate']*100:.2f}%)")
    
    # Print token usage statistics if available
    token_usage = metrics.get('token_usage')
    if token_usage:
        print(f"{'-'*80}")
        print(f"Token Usage Statistics (samples: {token_usage.get('samples_with_usage', 0)}/{token_usage.get('total_samples', 0)}):")
        if 'prompt_tokens' in token_usage:
            pt = token_usage['prompt_tokens']
            print(f"  - Prompt Tokens: avg {pt['average']:.2f}, total {pt['total']}, range [{pt['min']}, {pt['max']}]")
        if 'completion_tokens' in token_usage:
            ct = token_usage['completion_tokens']
            print(f"  - Completion Tokens: avg {ct['average']:.2f}, total {ct['total']}, range [{ct['min']}, {ct['max']}]")
        if 'reasoning_tokens' in token_usage:
            rt = token_usage['reasoning_tokens']
            print(f"  - Reasoning Tokens: avg {rt['average']:.2f}, total {rt['total']}, range [{rt['min']}, {rt['max']}]")
        if 'total_tokens' in token_usage:
            tt = token_usage['total_tokens']
            print(f"  - Total Tokens: avg {tt['average']:.2f}, total {tt['total']}, range [{tt['min']}, {tt['max']}]")
        if 'cached_tokens' in token_usage:
            cct = token_usage['cached_tokens']
            print(f"  - Cached Tokens: avg {cct['average']:.2f}, total {cct['total']}, range [{cct['min']}, {cct['max']}]")
    
    print(f"{'='*80}")


def print_summary_table(all_results: List[Dict]):
    """
    Print summary table
    """
    print(f"\n\n{'='*120}")
    print(f"Summary Table")
    print(f"{'='*120}")
    
    # Check if ToolCalls-Trigger Similarity data exists
    has_similarity = any(r['metrics'].get('ToolCalls-Trigger-Similarity') is not None for r in all_results)
    
    # Header
    if has_similarity:
        print(f"\n{'File':<40} {'Model':<30} {'Query-Success-Rate':<20} {'ToolCalls-Match-Rate':<22} {'ToolCalls-Trigger-Sim':<22} {'ToolCalls-Schema-Acc':<22} {'Error-Only-Reasoning':<22} {'Language-Following':<20}")
        print(f"{'-'*198}")
    else:
        print(f"\n{'File':<40} {'Model':<30} {'Query-Success-Rate':<20} {'ToolCalls-Match-Rate':<22} {'ToolCalls-Schema-Acc':<22} {'Error-Only-Reasoning':<22} {'Language-Following':<20}")
        print(f"{'-'*176}")
    
    # Data rows
    for result in all_results:
        file_name = os.path.basename(result['file_path'])
        model = result['data'].get('model', 'Unknown')
        if len(model) > 28:
            model = model[:25] + "..."
        metrics = result['metrics']
        
        if has_similarity:
            sim_f1 = metrics.get('ToolCalls-Trigger-Similarity')
            sim_str = f"{sim_f1*100:>20.2f}%" if sim_f1 is not None else "N/A".rjust(22)
            print(f"{file_name:<40} {model:<30} {metrics['Query-Success-Rate']*100:>18.2f}% {metrics['ToolCalls-Match-Rate']*100:>20.2f}% {sim_str} {metrics['ToolCalls-Schema-Accuracy']*100:>20.2f}% {metrics['Error-Only-Reasoning-Rate']*100:>20.2f}% {metrics['Language-Following-Success-Rate']*100:>18.2f}%")
        else:
            print(f"{file_name:<40} {model:<30} {metrics['Query-Success-Rate']*100:>18.2f}% {metrics['ToolCalls-Match-Rate']*100:>20.2f}% {metrics['ToolCalls-Schema-Accuracy']*100:>20.2f}% {metrics['Error-Only-Reasoning-Rate']*100:>20.2f}% {metrics['Language-Following-Success-Rate']*100:>18.2f}%")
    
    if has_similarity:
        print(f"{'='*198}")
    else:
        print(f"{'='*176}")
    
    # Calculate averages
    if all_results:
        avg_metrics = {
            'Query-Success-Rate': sum(r['metrics']['Query-Success-Rate'] for r in all_results) / len(all_results),
            'ToolCalls-Match-Rate': sum(r['metrics']['ToolCalls-Match-Rate'] for r in all_results) / len(all_results),
            'ToolCalls-Schema-Accuracy': sum(r['metrics']['ToolCalls-Schema-Accuracy'] for r in all_results) / len(all_results),
            'Error-Only-Reasoning-Rate': sum(r['metrics']['Error-Only-Reasoning-Rate'] for r in all_results) / len(all_results),
            'Language-Following-Success-Rate': sum(r['metrics']['Language-Following-Success-Rate'] for r in all_results) / len(all_results),
        }
        
        # Calculate ToolCalls-Trigger Similarity average
        if has_similarity:
            sim_values = [r['metrics']['ToolCalls-Trigger-Similarity'] for r in all_results if r['metrics'].get('ToolCalls-Trigger-Similarity') is not None]
            if sim_values:
                avg_metrics['ToolCalls-Trigger-Similarity'] = sum(sim_values) / len(sim_values)

        # Calculate Scenario-Check-Pass-Rate average
        scenario_values = [r['metrics']['Scenario-Check-Pass-Rate'] for r in all_results if r['metrics'].get('Scenario-Check-Pass-Rate') is not None]
        if scenario_values:
            avg_metrics['Scenario-Check-Pass-Rate'] = sum(scenario_values) / len(scenario_values)
        
        print(f"\nAverages:")
        print(f"  1. Query-Success-Rate: {avg_metrics['Query-Success-Rate']:.4f} ({avg_metrics['Query-Success-Rate']*100:.2f}%)")
        print(f"  2. ToolCalls-Match-Rate: {avg_metrics['ToolCalls-Match-Rate']:.4f} ({avg_metrics['ToolCalls-Match-Rate']*100:.2f}%)")
        if has_similarity and 'ToolCalls-Trigger-Similarity' in avg_metrics:
            print(f"  3. ToolCalls-Trigger-Similarity: {avg_metrics['ToolCalls-Trigger-Similarity']:.4f} ({avg_metrics['ToolCalls-Trigger-Similarity']*100:.2f}%)")
        print(f"  4. ToolCalls-Schema-Accuracy: {avg_metrics['ToolCalls-Schema-Accuracy']:.4f} ({avg_metrics['ToolCalls-Schema-Accuracy']*100:.2f}%)")
        print(f"  5. Error-Only-Reasoning-Rate: {avg_metrics['Error-Only-Reasoning-Rate']:.4f} ({avg_metrics['Error-Only-Reasoning-Rate']*100:.2f}%)")
        print(f"  6. Language-Following-Success-Rate: {avg_metrics['Language-Following-Success-Rate']:.4f} ({avg_metrics['Language-Following-Success-Rate']*100:.2f}%)")
        if 'Scenario-Check-Pass-Rate' in avg_metrics:
            print(f"  7. Scenario-Check-Pass-Rate: {avg_metrics['Scenario-Check-Pass-Rate']:.4f} ({avg_metrics['Scenario-Check-Pass-Rate']*100:.2f}%)")
        
        # Calculate Token usage averages
        token_usage_results = [r['metrics'].get('token_usage') for r in all_results if r['metrics'].get('token_usage')]
        if token_usage_results:
            print(f"\n  Token Usage Statistics Averages:")
            avg_token_usage = calculate_average_token_usage(token_usage_results)
            if 'prompt_tokens' in avg_token_usage:
                print(f"    - Avg Prompt Tokens: {avg_token_usage['prompt_tokens']['average']:.2f}")
            if 'completion_tokens' in avg_token_usage:
                print(f"    - Avg Completion Tokens: {avg_token_usage['completion_tokens']['average']:.2f}")
            if 'reasoning_tokens' in avg_token_usage:
                print(f"    - Avg Reasoning Tokens: {avg_token_usage['reasoning_tokens']['average']:.2f}")
            if 'total_tokens' in avg_token_usage:
                print(f"    - Avg Total Tokens: {avg_token_usage['total_tokens']['average']:.2f}")
            if 'cached_tokens' in avg_token_usage:
                print(f"    - Avg Cached Tokens: {avg_token_usage['cached_tokens']['average']:.2f}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch calculate metrics')
    parser.add_argument('--root-dir', type=str, default='.',
                        help='Root directory path, defaults to current directory')
    parser.add_argument('--provider', type=str, default=None,
                        help='Specify provider name, only calculate files for that provider, i.e. {provider}_summary.json')
    parser.add_argument('--detailed', action='store_true',
                        help='Whether to show detailed information')
    parser.add_argument('--output', type=str, default=None,
                        help='Output results to JSON file')
    parser.add_argument('--sample-file', type=str, default=None,
                        help='sample.jsonl file path, used to count expected_tool_call as Match-Rate denominator')
    parser.add_argument('--no-similarity', action='store_true',
                        help='Skip ToolCalls-Trigger Similarity (F1) computation entirely')
    
    args = parser.parse_args()
    
    # Read expected_tool_call statistics (for Match-Rate denominator)
    sample_file = Path(args.sample_file) if args.sample_file else DEFAULT_SAMPLE_FILE
    expected_tool_call_stats = get_expected_tool_call_count(sample_file)
    if expected_tool_call_stats['total'] > 0:
        print(f"Read expected_tool_call statistics from {sample_file}:")
        print(f"  - expected_tool_call=True: {expected_tool_call_stats['true']}")
        print(f"  - expected_tool_call=False: {expected_tool_call_stats['false']}")
        print(f"  - Total (Match-Rate denominator): {expected_tool_call_stats['total']}")
    
    # Find all summary files
    print(f"Searching directory: {os.path.abspath(args.root_dir)}")
    if args.provider:
        print(f"Specified provider: {args.provider}")
    
    summary_files = find_summary_files(args.root_dir, args.provider)
    
    print(f"\nTotal {len(summary_files)} files found")
    
    if len(summary_files) == 0:
        if args.provider:
            print(f"No {args.provider}_summary.json files found")
        else:
            print("No *_summary.json files found")
        return
    
    print("\nFiles found:")
    for i, file_path in enumerate(summary_files, 1):
        print(f"  {i}. {file_path}")
    
    # Process each file
    all_results = []
    # Cache reference data by version to avoid duplicate loading
    reference_cache: Dict[str, Optional[List[Dict]]] = {}

    for file_path in summary_files:
        data = load_summary_data(file_path)
        if data is None:
            continue

        metrics = calculate_metrics(data, expected_tool_call_stats)

        result = {
            'file_path': file_path,
            'data': data,
            'metrics': metrics
        }

        # Calculate ToolCalls-Trigger-Similarity
        # Skip condition: specified provider is minimax itself
        is_minimax_self = args.provider and args.provider.lower() == 'minimax'
        if args.no_similarity:
            metrics['ToolCalls-Trigger-Similarity'] = None
        elif not is_minimax_self:
            results_file = file_path.replace('_summary.json', '_results.jsonl')
            if os.path.exists(results_file):
                model_results = load_jsonl(results_file)
                if model_results is not None:
                    # Auto-detect version from model name, select corresponding reference folder
                    model_name = data.get('model', '')
                    version = detect_model_version(model_name)
                    if version is None:
                        # Fallback: search in root_dir using old logic
                        print(f"Warning: Cannot detect version from model name '{model_name}', trying to find reference data in root_dir")
                        version = '__legacy__'

                    if version not in reference_cache:
                        if version == '__legacy__':
                            reference_cache[version] = load_minimax_reference(args.root_dir)
                        else:
                            reference_cache[version] = load_minimax_reference_by_version(version)

                    minimax_reference = reference_cache[version]

                    if minimax_reference is not None:
                        try:
                            min_len = min(len(minimax_reference), len(model_results))
                            if len(minimax_reference) != len(model_results):
                                print(f"Warning: Sample count mismatch (minimax: {len(minimax_reference)}, model: {len(model_results)}), using first {min_len} samples for calculation")
                            ref_subset = minimax_reference[:min_len]
                            model_subset = model_results[:min_len]

                            f1_metrics = calculate_tool_call_f1(ref_subset, model_subset)
                            result['toolcalls_trigger_similarity'] = {
                                'f1': f1_metrics['f1'],
                                'precision': f1_metrics['precision'],
                                'recall': f1_metrics['recall'],
                                'tp': f1_metrics['tp'],
                                'fp': f1_metrics['fp'],
                                'fn': f1_metrics['fn'],
                                'tn': f1_metrics['tn'],
                                'samples_used': min_len,
                                'reference_version': version,
                            }
                            metrics['ToolCalls-Trigger-Similarity'] = f1_metrics['f1']
                        except Exception as e:
                            print(f"Warning: Error calculating ToolCalls-Trigger Similarity for {file_path}: {e}")
                            metrics['ToolCalls-Trigger-Similarity'] = None
                    else:
                        metrics['ToolCalls-Trigger-Similarity'] = None
            else:
                print(f"Warning: Corresponding results file not found: {results_file}")
                metrics['ToolCalls-Trigger-Similarity'] = None
        else:
            metrics['ToolCalls-Trigger-Similarity'] = None

        all_results.append(result)
        
        if args.detailed:
            print_file_metrics(file_path, data, metrics)
    
    # Print summary table
    print_summary_table(all_results)
    
    # Save to file
    if args.output:
        # Calculate averages
        avg_metrics = {}
        if all_results:
            avg_metrics_raw = {
                'Query-Success-Rate': sum(r['metrics']['Query-Success-Rate'] for r in all_results) / len(all_results),
                'ToolCalls-Match-Rate': sum(r['metrics']['ToolCalls-Match-Rate'] for r in all_results) / len(all_results),
                'ToolCalls-Schema-Accuracy': sum(r['metrics']['ToolCalls-Schema-Accuracy'] for r in all_results) / len(all_results),
                'Error-Only-Reasoning-Rate': sum(r['metrics']['Error-Only-Reasoning-Rate'] for r in all_results) / len(all_results),
                'Language-Following-Success-Rate': sum(r['metrics']['Language-Following-Success-Rate'] for r in all_results) / len(all_results),
            }
            
            # Calculate ToolCalls-Trigger Similarity average
            sim_values = [r['metrics']['ToolCalls-Trigger-Similarity'] for r in all_results if r['metrics'].get('ToolCalls-Trigger-Similarity') is not None]
            if sim_values:
                avg_metrics_raw['ToolCalls-Trigger-Similarity'] = sum(sim_values) / len(sim_values)

            # Calculate Scenario-Check-Pass-Rate average
            scenario_values = [r['metrics']['Scenario-Check-Pass-Rate'] for r in all_results if r['metrics'].get('Scenario-Check-Pass-Rate') is not None]
            if scenario_values:
                avg_metrics_raw['Scenario-Check-Pass-Rate'] = sum(scenario_values) / len(scenario_values)
            
            # Calculate Token usage averages
            token_usage_results = [r['metrics'].get('token_usage') for r in all_results if r['metrics'].get('token_usage')]
            if token_usage_results:
                avg_metrics_raw['token_usage'] = calculate_average_token_usage(token_usage_results)
            
            # Reorganize averages with numbered prefix in specified order
            avg_metrics = {
                '1. Query-Success-Rate': avg_metrics_raw['Query-Success-Rate'],
                '2. ToolCalls-Match-Rate': avg_metrics_raw['ToolCalls-Match-Rate'],
            }
            
            # Add ToolCalls-Trigger-Similarity (if exists)
            if 'ToolCalls-Trigger-Similarity' in avg_metrics_raw:
                avg_metrics['3. ToolCalls-Trigger-Similarity'] = avg_metrics_raw['ToolCalls-Trigger-Similarity']
            
            avg_metrics.update({
                '4. ToolCalls-Schema-Accuracy': avg_metrics_raw['ToolCalls-Schema-Accuracy'],
                '5. Error-Only-Reasoning-Rate': avg_metrics_raw['Error-Only-Reasoning-Rate'],
                '6. Language-Following-Success-Rate': avg_metrics_raw['Language-Following-Success-Rate']
            })

            # Add Scenario-Check-Pass-Rate (if exists)
            if 'Scenario-Check-Pass-Rate' in avg_metrics_raw:
                avg_metrics['7. Scenario-Check-Pass-Rate'] = avg_metrics_raw['Scenario-Check-Pass-Rate']

            # Add Token usage statistics (if exists)
            if 'token_usage' in avg_metrics_raw:
                avg_metrics['8. Token-Usage'] = avg_metrics_raw['token_usage']
        
        # Build output data structure
        output_data = {
            'summary': {
                'total_files': len(all_results),
                'average_metrics': avg_metrics
            },
            'results': []
        }
        
        for result in all_results:
            metrics = result['metrics']
            
            # Reorganize metrics with numbered prefix in specified order
            ordered_metrics = {
                '1. Query-Success-Rate': metrics['Query-Success-Rate'],
                '2. ToolCalls-Match-Rate': metrics['ToolCalls-Match-Rate'],
            }
            
            # Add ToolCalls-Trigger-Similarity (if exists)
            if metrics.get('ToolCalls-Trigger-Similarity') is not None:
                ordered_metrics['3. ToolCalls-Trigger-Similarity'] = metrics['ToolCalls-Trigger-Similarity']
            
            ordered_metrics.update({
                '4. ToolCalls-Schema-Accuracy': metrics['ToolCalls-Schema-Accuracy'],
                '5. Error-Only-Reasoning-Rate': metrics['Error-Only-Reasoning-Rate'],
                '6. Language-Following-Success-Rate': metrics['Language-Following-Success-Rate']
            })

            # Add Scenario-Check-Pass-Rate (if exists)
            if metrics.get('Scenario-Check-Pass-Rate') is not None:
                ordered_metrics['7. Scenario-Check-Pass-Rate'] = metrics['Scenario-Check-Pass-Rate']

            # Add Token usage statistics (if exists)
            if metrics.get('token_usage'):
                ordered_metrics['8. Token-Usage'] = metrics['token_usage']
            
            result_data = {
                'file': result['file_path'],
                'model': result['data'].get('model', 'Unknown'),
                'metrics': ordered_metrics
            }
            
            # Include ToolCalls-Trigger Similarity detailed data if available
            if 'toolcalls_trigger_similarity' in result:
                result_data['toolcalls_trigger_similarity'] = result['toolcalls_trigger_similarity']
            
            output_data['results'].append(result_data)
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        
        print(f"\nResults saved to: {args.output}")


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Calculate tool call similarity metrics:
1. ToolCalls-Trigger Similarity (F1 Score)
2. Multi-ToolCalls-Trigger Similarity (based on Cosine similarity)
3. ToolCalls-Schema-Accuracy (tool call success rate)
4. Validation Metrics (error_repeating, language_following)
5. Error-Only-Reasoning-Rate (errors containing only reasoning)
"""

import json
import os
import glob
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import numpy as np
import argparse


def load_jsonl(file_path: str) -> List[Dict]:
    """Load JSONL file"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    return data


def load_summary(file_path: str) -> Dict:
    """Load summary JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def discover_models(folder_path: str) -> Dict[str, Dict[str, str]]:
    """
    Scan folder to discover summary and results files for all models
    
    Args:
        folder_path: Folder path containing result files
    
    Returns:
        {
            'model_name': {
                'summary': '/path/to/model_summary.json',
                'results': '/path/to/model_results.jsonl'
            },
            ...
        }
    """
    models = {}
    folder_path = Path(folder_path)
    
    # Find all *_summary.json files
    summary_files = glob.glob(str(folder_path / '*_summary.json'))
    
    for summary_file in summary_files:
        summary_file = Path(summary_file)
        filename = summary_file.stem  # Remove extension
        
        # Extract model name (part before _summary)
        if filename.endswith('_summary'):
            model_name = filename[:-8]  # Remove '_summary'
        else:
            continue
        
        # Find corresponding results.jsonl file
        results_file = folder_path / f'{model_name}_results.jsonl'
        
        if results_file.exists():
            models[model_name] = {
                'summary': str(summary_file),
                'results': str(results_file)
            }
        else:
            print(f"Warning: Found {summary_file.name} but not corresponding {model_name}_results.jsonl")
    
    return models


def get_finish_reason(result: Dict) -> str:
    """Get finish_reason, always return a string"""
    try:
        if not result or 'response' not in result:
            return 'error_no_response'
        
        response = result.get('response')
        if response is None:
            return 'error_response_none'
        
        choices = response.get('choices')
        if choices is None:
            return 'error_choices_none'
        
        if len(choices) == 0:
            return 'error_choices_empty'
        
        finish_reason = choices[0].get('finish_reason')
        if finish_reason is None:
            return 'error_no_finish_reason'
        
        return str(finish_reason)
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        return f'error_exception_{type(e).__name__}'


def calculate_tool_call_f1(official_results: List[Dict], model_results: List[Dict]) -> Dict:
    """
    Calculate ToolCalls-Trigger Similarity (F1 Score)
    
    Args:
        official_results: Gold standard results
        model_results: Model results to evaluate
    
    Returns:
        Dict containing TP, FP, FN, TN, precision, recall, f1
    """
    if len(official_results) != len(model_results):
        raise ValueError(f"Sample count mismatch: gold standard {len(official_results)}, evaluated {len(model_results)}")
    
    tp = fp = fn = tn = 0
    error_count = 0
    error_detail = {}
    
    for official, model in zip(official_results, model_results):
        official_reason = get_finish_reason(official)
        model_reason = get_finish_reason(model)
        
        # Count error cases
        if model_reason.startswith('error_'):
            error_count += 1
            error_detail[model_reason] = error_detail.get(model_reason, 0) + 1
        
        official_is_tool_call = (official_reason == 'tool_calls')
        model_is_tool_call = (model_reason == 'tool_calls')
        
        if official_is_tool_call and model_is_tool_call:
            tp += 1
        elif not official_is_tool_call and model_is_tool_call:
            fp += 1
        elif official_is_tool_call and not model_is_tool_call:
            fn += 1
        else:
            tn += 1
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'tn': tn,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'total_samples': len(official_results),
        'error_count': error_count,
        'error_detail': error_detail
    }


def normalize_distribution(dist_dict: Dict[str, int]) -> Tuple[List[int], List[float]]:
    """
    Normalize distribution dict to probability distribution
    
    Args:
        dist_dict: {"1": 20, "2": 15, ...}
    
    Returns:
        (keys, probabilities): Sorted key list and corresponding probability list
    """
    keys = sorted([int(k) for k in dist_dict.keys()])
    counts = [dist_dict[str(k)] for k in keys]
    total = sum(counts)
    
    if total == 0:
        return keys, [0.0] * len(keys)
    
    probs = [count / total for count in counts]
    return keys, probs


def align_distributions(keys1: List[int], probs1: List[float], 
                        keys2: List[int], probs2: List[float]) -> Tuple[List[int], List[float], List[float]]:
    """Align two distributions to ensure they have the same keys"""
    all_keys = sorted(set(keys1 + keys2))
    
    dict1 = dict(zip(keys1, probs1))
    dict2 = dict(zip(keys2, probs2))
    
    aligned_probs1 = [dict1.get(k, 0.0) for k in all_keys]
    aligned_probs2 = [dict2.get(k, 0.0) for k in all_keys]
    
    return all_keys, aligned_probs1, aligned_probs2


def cosine_similarity(probs1: List[float], probs2: List[float]) -> float:
    """
    Calculate cosine similarity
    
    Returns:
        Similarity in range [0, 1], 1 means identical
    """
    vec1 = np.array(probs1)
    vec2 = np.array(probs2)
    
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    cos_sim = np.dot(vec1, vec2) / (norm1 * norm2)
    return float(cos_sim)


def calculate_toolcall_schema_accuracy(summary: Dict) -> Dict:
    """
    Calculate ToolCalls-Schema-Accuracy
    
    Args:
        summary: Model's summary data
    
    Returns:
        Dict containing success rate metrics
    """
    tool_calls_finish = summary.get('tool_calls_finish_tool_calls', 0)
    tool_calls_successful = summary.get('tool_calls_successful_count', 0)
    
    accuracy = tool_calls_successful / tool_calls_finish if tool_calls_finish > 0 else 0.0
    
    return {
        'accuracy': accuracy,
        'tool_calls_successful_count': tool_calls_successful,
        'tool_calls_finish_tool_calls': tool_calls_finish
    }


def calculate_error_only_reasoning(results: List[Dict]) -> Dict:
    """
    Check if there are errors with only reasoning while content and tool_calls are empty
    
    Args:
        results: Model's result list
    
    Returns:
        Dict containing error_only_reasoning statistics
    """
    error_only_reasoning_count = 0
    total_checked = len(results)
    
    for result in results:
        try:
            if not result or 'response' not in result:
                continue
            
            response = result.get('response')
            if response is None:
                continue
            
            choices = response.get('choices')
            if choices is None or len(choices) == 0:
                continue
            
            message = choices[0].get('message')
            if message is None:
                continue
            
            # Check reasoning, content, tool_calls
            reasoning = message.get('reasoning_content') or message.get('reasoning', '')
            content = message.get('content', '')
            tool_calls = message.get('tool_calls', [])
            
            # If reasoning has content, but content and tool_calls are empty
            if reasoning and not content and not tool_calls:
                error_only_reasoning_count += 1
                
        except (KeyError, IndexError, TypeError, AttributeError):
            continue
    
    error_only_reasoning_rate = error_only_reasoning_count / total_checked if total_checked > 0 else 0.0
    
    return {
        'error_only_reasoning_count': error_only_reasoning_count,
        'total_checked': total_checked,
        'error_only_reasoning_rate': error_only_reasoning_rate
    }


def calculate_validation_metrics(summary: Dict) -> Dict:
    """
    Calculate validation metrics (error_repeating and language_following)
    
    Args:
        summary: Model's summary data
    
    Returns:
        Dict containing validation metrics
    """
    # error_repeating metrics
    error_repeating_checked = summary.get('error_repeating_checked_count', 0)
    error_repeating_valid = summary.get('error_repeating_valid_count', 0)
    error_repeating_invalid = summary.get('error_repeating_invalid_count', 0)
    
    error_repeating_success_rate = error_repeating_valid / error_repeating_checked if error_repeating_checked > 0 else 0.0
    
    # language_following metrics
    language_following_checked = summary.get('language_following_checked_count', 0)
    language_following_valid = summary.get('language_following_valid_count', 0)
    language_following_invalid = summary.get('language_following_invalid_count', 0)
    
    language_following_success_rate = language_following_valid / language_following_checked if language_following_checked > 0 else 0.0
    
    # Overall success rate (sum of two validation rules)
    total_checked = error_repeating_checked + language_following_checked
    total_valid = error_repeating_valid + language_following_valid
    total_invalid = error_repeating_invalid + language_following_invalid
    
    overall_success_rate = total_valid / total_checked if total_checked > 0 else 0.0
    
    return {
        'error_repeating': {
            'checked_count': error_repeating_checked,
            'valid_count': error_repeating_valid,
            'invalid_count': error_repeating_invalid,
            'success_rate': error_repeating_success_rate
        },
        'language_following': {
            'checked_count': language_following_checked,
            'valid_count': language_following_valid,
            'invalid_count': language_following_invalid,
            'success_rate': language_following_success_rate
        },
        'overall': {
            'total_checked': total_checked,
            'total_valid': total_valid,
            'total_invalid': total_invalid,
            'overall_success_rate': overall_success_rate
        }
    }


def calculate_multi_toolcall_similarity(official_dist: Dict[str, int], 
                                       model_dist: Dict[str, int]) -> Dict:
    """
    Calculate Multi-ToolCalls-Trigger Similarity (based on Cosine similarity)
    
    Args:
        official_dist: Gold standard's tool_calls_count_distribution
        model_dist: Evaluated model's tool_calls_count_distribution
    
    Returns:
        Dict containing similarity metrics and distribution comparison
    """
    # Normalize distributions
    keys1, probs1 = normalize_distribution(official_dist)
    keys2, probs2 = normalize_distribution(model_dist)
    
    # Align distributions
    all_keys, aligned_probs1, aligned_probs2 = align_distributions(keys1, probs1, keys2, probs2)
    
    # Calculate Cosine similarity
    similarity = cosine_similarity(aligned_probs1, aligned_probs2)
    
    # Build detailed distribution comparison
    distribution_comparison = []
    for key, prob1, prob2 in zip(all_keys, aligned_probs1, aligned_probs2):
        count1 = official_dist.get(str(key), 0)
        count2 = model_dist.get(str(key), 0)
        distribution_comparison.append({
            'tool_calls_count': key,
            'official_count': count1,
            'official_prob': prob1,
            'model_count': count2,
            'model_prob': prob2,
            'prob_diff': prob2 - prob1
        })
    
    return {
        'cosine_similarity': similarity,
        'distribution_comparison': distribution_comparison
    }


def print_results(model_name: str, f1_metrics: Dict, multi_metrics: Dict, accuracy_metrics: Dict, 
                  validation_metrics: Dict, error_only_reasoning_metrics: Dict):
    """Print comprehensive results"""
    print(f"\n{'='*70}")
    print(f"Model: {model_name}")
    print(f"{'='*70}")
    
    # 1. ToolCall-Trigger Similarity (tool_call_f1)
    print(f"\n1. ToolCalls-Trigger Similarity (whether tool_calls triggered)")
    print(f"   Confusion Matrix:")
    print(f"     TP: {f1_metrics['tp']:3d}  |  FP: {f1_metrics['fp']:3d}")
    print(f"     FN: {f1_metrics['fn']:3d}  |  TN: {f1_metrics['tn']:3d}")
    print(f"   Performance Metrics:")
    print(f"     Precision: {f1_metrics['precision']:.4f} ({f1_metrics['precision']*100:.2f}%)")
    print(f"     Recall:    {f1_metrics['recall']:.4f} ({f1_metrics['recall']*100:.2f}%)")
    print(f"     F1 Score:  {f1_metrics['f1']:.4f} ({f1_metrics['f1']*100:.2f}%)")
    print(f"   Special Cases:")
    print(f"     Error count: {f1_metrics['error_count']} / {f1_metrics['total_samples']}")
    if f1_metrics['error_detail']:
        print(f"     Error details:")
        for error_type, count in sorted(f1_metrics['error_detail'].items()):
            print(f"       {error_type}: {count}")
    
    # 2. Multi-ToolCalls-Trigger Similarity
    print(f"\n2. Multi-ToolCalls-Trigger Similarity (tool_calls count distribution)")
    print(f"   Cosine Similarity: {multi_metrics['cosine_similarity']:.4f} ({multi_metrics['cosine_similarity']*100:.2f}%)")
    
    print(f"\n   Detailed Distribution Comparison:")
    print(f"   {'Tool Calls':<12} {'Official Count':<15} {'Official Prob':<15} {'Model Count':<12} {'Model Prob':<12} {'Prob Diff':<12}")
    print(f"   {'-'*78}")
    for item in multi_metrics['distribution_comparison']:
        print(f"   {item['tool_calls_count']:<12} "
              f"{item['official_count']:<10} "
              f"{item['official_prob']:<12.4f} "
              f"{item['model_count']:<10} "
              f"{item['model_prob']:<12.4f} "
              f"{item['prob_diff']:+12.4f}")
    
    # 3. ToolCalls-Schema-Accuracy (tool call success rate)
    print(f"\n3. ToolCalls-Schema-Accuracy (tool call success rate)")
    print(f"   Success rate: {accuracy_metrics['accuracy']:.4f} ({accuracy_metrics['accuracy']*100:.2f}%)")
    print(f"   Successful:   {accuracy_metrics['tool_calls_successful_count']}")
    print(f"   Total:        {accuracy_metrics['tool_calls_finish_tool_calls']}")
    
    # 4. Validation Metrics
    print(f"\n4. Validation Metrics")
    
    # Error Repeating
    error_repeating = validation_metrics['error_repeating']
    print(f"   Error Repeating:")
    print(f"     Checked:   {error_repeating['checked_count']}")
    print(f"     Valid:     {error_repeating['valid_count']}")
    print(f"     Invalid:   {error_repeating['invalid_count']}")
    print(f"     Success rate: {error_repeating['success_rate']:.4f} ({error_repeating['success_rate']*100:.2f}%)")
    
    # Language Following
    language_following = validation_metrics['language_following']
    print(f"   Language Following:")
    print(f"     Checked:   {language_following['checked_count']}")
    print(f"     Valid:     {language_following['valid_count']}")
    print(f"     Invalid:   {language_following['invalid_count']}")
    print(f"     Success rate: {language_following['success_rate']:.4f} ({language_following['success_rate']*100:.2f}%)")
    
    # Overall
    overall = validation_metrics['overall']
    print(f"   Overall:")
    print(f"     Total checked: {overall['total_checked']}")
    print(f"     Total valid:   {overall['total_valid']}")
    print(f"     Total invalid: {overall['total_invalid']}")
    print(f"     Overall success rate: {overall['overall_success_rate']:.4f} ({overall['overall_success_rate']*100:.2f}%)")
    
    # 5. Error Only Reasoning (errors containing only reasoning)
    print(f"\n5. Error Only Reasoning (errors containing only reasoning)")
    print(f"   Error count:  {error_only_reasoning_metrics['error_only_reasoning_count']}")
    print(f"   Total checked: {error_only_reasoning_metrics['total_checked']}")
    print(f"   Error rate:    {error_only_reasoning_metrics['error_only_reasoning_rate']:.4f} ({error_only_reasoning_metrics['error_only_reasoning_rate']*100:.2f}%)")


def main(folder_path: str = '/data/minimax-dialogue/users/xiaojun/MiniMax-Vendor-Verifier/batch_results', 
         reference_model: Optional[str] = None):
    """
    Main function: compare tool call similarity of all models in folder
    
    Args:
        folder_path: Folder path containing result files
        reference_model: Reference model name, if None, use first discovered model as reference
    """
    print("="*80)
    print("Tool Call Similarity Comprehensive Evaluation - Multi-Model Batch Comparison")
    print("="*80)
    
    # Discover all models
    print(f"\nScanning folder: {folder_path}")
    models = discover_models(folder_path)
    
    if not models:
        print(f"Error: No model files found in {folder_path}")
        return
    
    model_names = sorted(models.keys())
    print(f"\nDiscovered {len(model_names)} models: {', '.join(model_names)}")
    
    # Determine reference model
    if reference_model is None:
        reference_model = model_names[0]
        print(f"No reference model specified, using first model as reference: {reference_model}")
    elif reference_model not in models:
        print(f"Error: Reference model '{reference_model}' does not exist")
        print(f"Available models: {', '.join(model_names)}")
        return
    else:
        print(f"Using specified reference model: {reference_model}")
    
    # Load reference model data
    print(f"\nLoading reference model data...")
    ref_results = load_jsonl(models[reference_model]['results'])
    ref_summary = load_summary(models[reference_model]['summary'])
    print(f"  Reference model ({reference_model}): {len(ref_results)} samples")
    
    # Load all other model data
    print(f"\nLoading other model data...")
    all_models_data = {
        reference_model: {
            'results': ref_results,
            'summary': ref_summary
        }
    }
    
    for model_name in model_names:
        if model_name != reference_model:
            results = load_jsonl(models[model_name]['results'])
            summary = load_summary(models[model_name]['summary'])
            all_models_data[model_name] = {
                'results': results,
                'summary': summary
            }
            print(f"  {model_name}: {len(results)} samples")
    
    # Calculate similarity between all models and reference model
    all_metrics = {}
    
    for model_name in model_names:
        if model_name == reference_model:
            # Reference model compared with itself (perfect match)
            continue
        
        model_results = all_models_data[model_name]['results']
        model_summary = all_models_data[model_name]['summary']
        
        # Calculate ToolCalls-Trigger Similarity
        f1_metrics = calculate_tool_call_f1(ref_results, model_results)

        # Calculate Multi-ToolCalls-Trigger Similarity (Cosine)
        multi_metrics = calculate_multi_toolcall_similarity(
            ref_summary['tool_calls_count_distribution'],
            model_summary['tool_calls_count_distribution']
        )
        
        # Calculate ToolCalls-Schema-Accuracy
        accuracy_metrics = calculate_toolcall_schema_accuracy(model_summary)
        
        # Calculate Validation Metrics
        validation_metrics = calculate_validation_metrics(model_summary)
        
        # Calculate Error Only Reasoning (errors containing only reasoning)
        error_only_reasoning_metrics = calculate_error_only_reasoning(model_results)
        
        all_metrics[model_name] = {
            'f1_metrics': f1_metrics,
            'multi_metrics': multi_metrics,
            'accuracy_metrics': accuracy_metrics,
            'validation_metrics': validation_metrics,
            'error_only_reasoning_metrics': error_only_reasoning_metrics
        }
        
        # Print detailed results for this model
        print_results(model_name, f1_metrics, multi_metrics, accuracy_metrics, validation_metrics, error_only_reasoning_metrics)
    
    # Print comparison summary for all models
    if len(model_names) > 1:
        print(f"\n{'='*80}")
        print(f"All Models Comparison Summary (Reference Model: {reference_model})")
        print(f"{'='*80}")
        
        # Prepare header
        header = f"{'Metric':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                header += f" {model_name:<15}"
        print(f"\n{header}")
        print(f"{'-'*80}")
        
        # F1 Score
        row = f"{'ToolCalls-Trigger Similarity':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                f1 = all_metrics[model_name]['f1_metrics']['f1']
                row += f" {f1:.4f}         "
        print(row)
        
        # Precision
        row = f"{'  - Precision':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                precision = all_metrics[model_name]['f1_metrics']['precision']
                row += f" {precision:.4f}         "
        print(row)
        
        # Recall
        row = f"{'  - Recall':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                recall = all_metrics[model_name]['f1_metrics']['recall']
                row += f" {recall:.4f}         "
        print(row)
        
        # Error Count
        row = f"{'  - Error Count':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                error_count = all_metrics[model_name]['f1_metrics']['error_count']
                total = all_metrics[model_name]['f1_metrics']['total_samples']
                row += f" {error_count}/{total}         "
        print(row)
        
        # Cosine Similarity
        row = f"{'Multi-ToolCalls-Trigger Similarity':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                cos_sim = all_metrics[model_name]['multi_metrics']['cosine_similarity']
                row += f" {cos_sim:.4f}         "
        print(row)
        
        # ToolCalls-Schema-Accuracy
        row = f"{'ToolCalls-Schema-Accuracy':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                accuracy = all_metrics[model_name]['accuracy_metrics']['accuracy']
                row += f" {accuracy:.4f}         "
        print(row)
        
        # Validation Metrics - Error Repeating Success Rate
        row = f"{'Error Repeating Success Rate':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                repeat_rate = all_metrics[model_name]['validation_metrics']['error_repeating']['success_rate']
                row += f" {repeat_rate:.4f}         "
        print(row)
        
        # Validation Metrics - Language Following Success Rate
        row = f"{'Language Following Success Rate':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                language_rate = all_metrics[model_name]['validation_metrics']['language_following']['success_rate']
                row += f" {language_rate:.4f}         "
        print(row)
        
        # Validation Metrics - Overall Success Rate
        row = f"{'Overall Validation Success Rate':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                overall_rate = all_metrics[model_name]['validation_metrics']['overall']['overall_success_rate']
                row += f" {overall_rate:.4f}         "
        print(row)
        
        # Error Only Reasoning Rate
        row = f"{'Error Only Reasoning Rate':<40}"
        for model_name in model_names:
            if model_name != reference_model:
                error_reasoning_rate = all_metrics[model_name]['error_only_reasoning_metrics']['error_only_reasoning_rate']
                row += f" {error_reasoning_rate:.4f}         "
        print(row)
    
    # Save results
    output = {
        'reference_model': reference_model,
        'models': {}
    }
    
    for model_name in model_names:
        if model_name == reference_model:
            continue
            
        output['models'][model_name] = {
            'toolcall_trigger_similarity': {
                'tp': all_metrics[model_name]['f1_metrics']['tp'],
                'fp': all_metrics[model_name]['f1_metrics']['fp'],
                'fn': all_metrics[model_name]['f1_metrics']['fn'],
                'tn': all_metrics[model_name]['f1_metrics']['tn'],
                'precision': all_metrics[model_name]['f1_metrics']['precision'],
                'recall': all_metrics[model_name]['f1_metrics']['recall'],
                'f1': all_metrics[model_name]['f1_metrics']['f1'],
                'error_count': all_metrics[model_name]['f1_metrics']['error_count'],
                'error_detail': all_metrics[model_name]['f1_metrics']['error_detail']
            },
            'multi_toolcall_trigger_similarity': {
                'cosine_similarity': all_metrics[model_name]['multi_metrics']['cosine_similarity'],
                'distribution_comparison': all_metrics[model_name]['multi_metrics']['distribution_comparison']
            },
            'toolcall_schema_accuracy': {
                'accuracy': all_metrics[model_name]['accuracy_metrics']['accuracy'],
                'tool_calls_successful_count': all_metrics[model_name]['accuracy_metrics']['tool_calls_successful_count'],
                'tool_calls_finish_tool_calls': all_metrics[model_name]['accuracy_metrics']['tool_calls_finish_tool_calls']
            },
            'validation_metrics': {
                'error_repeating': all_metrics[model_name]['validation_metrics']['error_repeating'],
                'language_following': all_metrics[model_name]['validation_metrics']['language_following'],
                'overall': all_metrics[model_name]['validation_metrics']['overall']
            },
            'error_only_reasoning': {
                'error_only_reasoning_count': all_metrics[model_name]['error_only_reasoning_metrics']['error_only_reasoning_count'],
                'total_checked': all_metrics[model_name]['error_only_reasoning_metrics']['total_checked'],
                'error_only_reasoning_rate': all_metrics[model_name]['error_only_reasoning_metrics']['error_only_reasoning_rate']
            }
        }
    
    output['metric_descriptions'] = {
        'toolcall_trigger_similarity': 'Measures whether the model correctly triggers tool_calls (F1 Score)',
        'multi_toolcall_trigger_similarity': 'Measures the similarity of count distribution when triggering multiple tool_calls (Cosine Similarity)',
        'toolcall_schema_accuracy': 'Measures the correctness rate of tool-call payloads (function name and arguments meeting the expected schema)',
        'validation_metrics': 'Measures the success rate of the model on various validation rules (error_repeating, language_following)',
        'error_only_reasoning': 'Measures whether the model has errors with only reasoning while content and tool_calls are empty'
    }
    
    output_file = os.path.join(folder_path, 'toolcall_similarity_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_file}")


if __name__ == '__main__':
    # Default uses batch_results folder
    # Can modify the following parameters to specify different folder and reference model
    args = argparse.ArgumentParser()
    args.add_argument('--folder_path', type=str, default='siliconflow_result')
    args.add_argument('--reference_model', type=str, default='minimax') # None means use first discovered model as reference, can also specify model name like 'minimax'
    args = args.parse_args()
    # Run evaluation
    main(folder_path=args.folder_path, reference_model=args.reference_model)
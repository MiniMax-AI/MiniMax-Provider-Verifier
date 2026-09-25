#!/bin/bash

#=============================================================================
# MiniMax Provider Verifier - Batch Verification Script
# 
# Usage: 
#   bash run_batch_sequential.sh \
#     --module 'test' \
#     --url 'https://api.example.com/v1/chat/completions' \
#     --model 'model-name' \
#     --api-key 'sk-xxx' \
#     --max-workers 10
#
# Parameters:
#   --module              Module name (required)
#   --url                 API URL (required)
#   --model               Model name (required)
#   --api-key             API Key (required)
#   --max-workers         Concurrent requests (default: 10)
#   --stream              Use streaming mode (default: false)
#   --debug               Debug mode, only run first 10 cases
#   --extra-body          Extra request body parameters (JSON format)
#   --mm-model            MiniMax baseline model name (default: MiniMax-M2.5)
#=============================================================================

echo "========================================="
echo "MiniMax Provider Verifier - Batch Verification"
echo "========================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

echo "📂 Project root: $PROJECT_ROOT"

# Default parameter values
MODULE=""
MAX_WORKERS="10"
STREAM_MODE=""
DEBUG_MODE=""
EXTRA_BODY=""
EXTRA_HEADERS=""
DIRECT_URL=""
DIRECT_MODEL=""
DIRECT_API_KEY=""
MM_MODEL="MiniMax-M2.5"
LOOP_COUNT="10"

# Parse command line arguments
echo "📋 Parsing command line arguments..."
while [[ $# -gt 0 ]]; do
    case $1 in
        --module)
            MODULE="$2"
            shift 2
            ;;
        --max-workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        --stream)
            STREAM_MODE="true"
            shift
            ;;
        --debug)
            DEBUG_MODE="true"
            shift
            ;;
        --extra-body)
            EXTRA_BODY="$2"
            shift 2
            ;;
        --extra-headers)
            EXTRA_HEADERS="$2"
            shift 2
            ;;
        --loop)
            LOOP_COUNT="$2"
            shift 2
            ;;
        --url)
            DIRECT_URL="$2"
            shift 2
            ;;
        --model)
            DIRECT_MODEL="$2"
            shift 2
            ;;
        --api-key)
            DIRECT_API_KEY="$2"
            shift 2
            ;;
        --mm-model)
            MM_MODEL="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Check required parameters
MISSING_PARAMS=""
if [ -z "$MODULE" ]; then
    MISSING_PARAMS="$MISSING_PARAMS --module"
fi
if [ -z "$DIRECT_URL" ]; then
    MISSING_PARAMS="$MISSING_PARAMS --url"
fi
if [ -z "$DIRECT_MODEL" ]; then
    MISSING_PARAMS="$MISSING_PARAMS --model"
fi
if [ -z "$DIRECT_API_KEY" ]; then
    MISSING_PARAMS="$MISSING_PARAMS --api-key"
fi

if [ -n "$MISSING_PARAMS" ]; then
    echo "❌ Error: Missing required parameters:$MISSING_PARAMS"
    echo ""
    echo "Usage:"
    echo "  bash run_batch_sequential.sh \\"
    echo "    --module 'test' \\"
    echo "    --url 'https://api.example.com/v1/chat/completions' \\"
    echo "    --model 'model-name' \\"
    echo "    --api-key 'sk-xxx' \\"
    echo "    --max-workers 10"
    echo ""
    echo "Parameters:"
    echo "  --module       Module name (required)"
    echo "  --url          API URL (required)"
    echo "  --model        Model name (required)"
    echo "  --api-key      API Key (required)"
    echo "  --max-workers  Concurrent requests (default: 10)"
    echo "  --stream       Use streaming mode"
    echo "  --debug        Debug mode"
    exit 1
fi

# Print parameters
echo ""
echo "✅ Parameters parsed:"
echo "  --module: $MODULE"
echo "  --url: $DIRECT_URL"
echo "  --model: $DIRECT_MODEL"
echo "  --api-key: ******"
echo "  --max-workers: $MAX_WORKERS"
echo "  --loop: $LOOP_COUNT"
echo "  --stream: ${STREAM_MODE:-false}"
echo "  --debug: ${DEBUG_MODE:-false}"
echo "  --mm-model: $MM_MODEL"

# Set output directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_BASE_DIR="$PROJECT_ROOT/output-dir/batch_${TIMESTAMP}"
echo ""
echo "📁 Loop mode: Will run $LOOP_COUNT times"
echo "📁 Output base directory: $OUTPUT_BASE_DIR"
mkdir -p "$OUTPUT_BASE_DIR"

# Check Python environment
echo ""
echo "========================================="
echo "🐍 Python Environment Check"
echo "========================================="

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "❌ Error: Python3 not found"
    exit 1
fi

echo "Using Python: $PYTHON_CMD"
echo "Python version: $($PYTHON_CMD --version)"

# Check if using uv
if command -v uv &> /dev/null; then
    echo "✅ Detected uv, will use uv run"
    USE_UV=1
else
    echo "ℹ️  uv not detected, will use python directly"
    USE_UV=0
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH}"
echo "✅ PYTHONPATH set"

# Create necessary directories
mkdir -p "$PROJECT_ROOT/logs"

echo ""
echo "========================================="
echo "🚀 Starting Batch Verification Tasks"
echo "========================================="

# Record all loop results
declare -a ALL_LOOPS_RESULTS

# Process URL: remove /chat/completions (OpenAI SDK will auto-append)
PROCESSED_URL="$DIRECT_URL"
if [[ "$DIRECT_URL" == */chat/completions ]]; then
    PROCESSED_URL="${DIRECT_URL%/chat/completions}"
    echo "⚠️  Detected URL contains /chat/completions, auto-removed"
fi

# Set MODEL_NAME environment variable
export MODEL_NAME="$DIRECT_MODEL"

# Outer loop: execute verification LOOP_COUNT times
for LOOP_IDX in $(seq 1 $LOOP_COUNT); do
    # Format loop number
    if [ $LOOP_IDX -lt 10 ]; then
        LOOP_NUM="0${LOOP_IDX}"
    else
        LOOP_NUM="${LOOP_IDX}"
    fi
    
    echo ""
    echo "========================================"
    echo "🔄 Loop ${LOOP_IDX}/${LOOP_COUNT}"
    echo "========================================"
    
    # Create loop output directory
    LOOP_OUTPUT_DIR="$OUTPUT_BASE_DIR/loop_${LOOP_NUM}"
    mkdir -p "$LOOP_OUTPUT_DIR"
    echo "📂 Loop output directory: $LOOP_OUTPUT_DIR"
    
    # Create module output directory
    MODULE_OUTPUT_DIR="$LOOP_OUTPUT_DIR/${MODULE}"
    mkdir -p "$MODULE_OUTPUT_DIR"
    
    # Generate log file
    LOG_FILE="$MODULE_OUTPUT_DIR/verifier.log"
    
    # Generate provider.json
    TEMP_PROVIDER="$MODULE_OUTPUT_DIR/provider.json"
    if [ -n "$EXTRA_HEADERS" ]; then
        cat > "$TEMP_PROVIDER" << EOF
[
  {
    "name": "$MODULE",
    "model": "$DIRECT_MODEL",
    "base_url": "$PROCESSED_URL",
    "api_key": "$DIRECT_API_KEY",
    "default_headers": $EXTRA_HEADERS
  }
]
EOF
    else
        cat > "$TEMP_PROVIDER" << EOF
[
  {
    "name": "$MODULE",
    "model": "$DIRECT_MODEL",
    "base_url": "$PROCESSED_URL",
    "api_key": "$DIRECT_API_KEY"
  }
]
EOF
    fi
    
    # Copy test data
    TEMP_JSONL="$MODULE_OUTPUT_DIR/test_data.jsonl"
    SAMPLE_JSONL="$PROJECT_ROOT/sample.jsonl"
    if [ -f "$SAMPLE_JSONL" ]; then
        cp "$SAMPLE_JSONL" "$TEMP_JSONL"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  sample.jsonl not found"
        ALL_LOOPS_RESULTS+=("LOOP_${LOOP_NUM}:FAILED")
        continue
    fi
    
    # Build verification command arguments
    VERIFY_ARGS="$TEMP_JSONL --provider-file $TEMP_PROVIDER --output-dir $MODULE_OUTPUT_DIR --parallel-providers 1 --max-workers $MAX_WORKERS"
    if [ "$STREAM_MODE" = "true" ]; then
        VERIFY_ARGS="$VERIFY_ARGS --stream"
    fi
    if [ "$DEBUG_MODE" = "true" ]; then
        VERIFY_ARGS="$VERIFY_ARGS --debug"
    fi
    
    # Build base command
    if [ $USE_UV -eq 1 ]; then
        BASE_CMD="uv run $PYTHON_CMD"
    else
        BASE_CMD="$PYTHON_CMD"
    fi
    
    # Execute verification
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🔍 Starting verification..."
    if [ -n "$EXTRA_BODY" ]; then
        $BASE_CMD "$SCRIPT_DIR/scripts/batch_verify.py" $VERIFY_ARGS --extra-body "$EXTRA_BODY" >> "$LOG_FILE" 2>&1
    else
        $BASE_CMD "$SCRIPT_DIR/scripts/batch_verify.py" $VERIFY_ARGS >> "$LOG_FILE" 2>&1
    fi
    
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Loop ${LOOP_IDX} completed successfully"
        ALL_LOOPS_RESULTS+=("LOOP_${LOOP_NUM}:SUCCESS")
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Loop ${LOOP_IDX} failed (exit code: ${EXIT_CODE})"
        ALL_LOOPS_RESULTS+=("LOOP_${LOOP_NUM}:FAILED")
    fi
done

# ========================================
# Statistics
# ========================================

echo ""
echo "=========================================="
echo "📊 All Verification Tasks Completed"
echo "=========================================="
echo "Total loops: $LOOP_COUNT"
echo ""

SUCCESSFUL_LOOPS=0
for result in "${ALL_LOOPS_RESULTS[@]}"; do
    IFS=':' read -ra PARTS <<< "$result"
    LOOP_NAME="${PARTS[0]}"
    STATUS="${PARTS[1]}"
    
    if [ "$STATUS" == "SUCCESS" ]; then
        SUCCESSFUL_LOOPS=$((SUCCESSFUL_LOOPS + 1))
        echo "  ✅ $LOOP_NAME: Success"
    else
        echo "  ❌ $LOOP_NAME: Failed"
    fi
done

echo ""
echo "Successful loops: ${SUCCESSFUL_LOOPS}/${LOOP_COUNT}"

if [ $SUCCESSFUL_LOOPS -eq 0 ]; then
    echo ""
    echo "⚠️  All tasks failed, cannot collect metrics"
    exit 1
fi

# ========================================
# Collect Metrics
# ========================================

echo ""
echo "=========================================="
echo "📈 Collecting Metrics"
echo "=========================================="

METRICS_REPORT="$OUTPUT_BASE_DIR/metrics_report.json"
REPORT_PROVIDER_NAME="$MODULE"

echo "📦 Using provider: $REPORT_PROVIDER_NAME"

if [ $USE_UV -eq 1 ]; then
    uv run $PYTHON_CMD "$SCRIPT_DIR/scripts/calculate_batch_metrics.py" \
        --root-dir "$OUTPUT_BASE_DIR" \
        --provider "$REPORT_PROVIDER_NAME" \
        --detailed \
        --output "$METRICS_REPORT"
else
    $PYTHON_CMD "$SCRIPT_DIR/scripts/calculate_batch_metrics.py" \
        --root-dir "$OUTPUT_BASE_DIR" \
        --provider "$REPORT_PROVIDER_NAME" \
        --detailed \
        --output "$METRICS_REPORT"
fi

if [ $? -eq 0 ]; then
    echo "✅ Metrics collection completed"
    echo "📊 Metrics report: $METRICS_REPORT"
else
    echo "⚠️  Metrics collection failed"
fi

# ========================================
# Compare with Baseline
# ========================================

BASELINE_DIR="$PROJECT_ROOT/output-dir/$MM_MODEL"
COMPARISON_REPORT="$OUTPUT_BASE_DIR/comparison_report.json"

if [ -d "$BASELINE_DIR" ]; then
    echo ""
    echo "=========================================="
    echo "📊 Comparing with Baseline"
    echo "=========================================="
    echo "📂 Baseline directory: $BASELINE_DIR"
    
    if [ $USE_UV -eq 1 ]; then
        uv run $PYTHON_CMD "$SCRIPT_DIR/scripts/compare_with_baseline.py" \
            --result-dir "$OUTPUT_BASE_DIR" \
            --baseline-dir "$BASELINE_DIR" \
            --provider "$REPORT_PROVIDER_NAME" \
            --output "$COMPARISON_REPORT"
    else
        $PYTHON_CMD "$SCRIPT_DIR/scripts/compare_with_baseline.py" \
            --result-dir "$OUTPUT_BASE_DIR" \
            --baseline-dir "$BASELINE_DIR" \
            --provider "$REPORT_PROVIDER_NAME" \
            --output "$COMPARISON_REPORT"
    fi
    
    if [ $? -eq 0 ]; then
        echo "✅ Baseline comparison completed"
        METRICS_REPORT="$COMPARISON_REPORT"
    fi
else
    echo ""
    echo "ℹ️  Baseline directory $BASELINE_DIR not found, skipping baseline comparison"
fi

# ========================================
# Complete
# ========================================

echo ""
echo "=========================================="
echo "🎉 All Tasks Completed!"
echo "=========================================="
echo "📂 Results saved at: $OUTPUT_BASE_DIR"
echo ""
echo "📊 Summary:"
echo "  - Total loops: $LOOP_COUNT"
echo "  - Successful loops: $SUCCESSFUL_LOOPS"
echo "  - Failed loops: $((LOOP_COUNT - SUCCESSFUL_LOOPS))"
echo "  - Metrics report: $METRICS_REPORT"
echo ""
echo "💡 View metrics:"
echo "   cat $METRICS_REPORT | jq '.summary'"
echo ""

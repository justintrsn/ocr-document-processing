#!/bin/bash

# OCR API Test Script with Options
# Supports both local files and OBS URLs with configurable options

# Default settings
API_URL="${API_URL:-http://localhost:8000}"
SOURCE_TYPE="${SOURCE_TYPE:-file}"  # file or obs
TEST_FILE="${TEST_FILE:-tests/documents/scanned_document.jpg}"
OBS_URL="${OBS_URL:-obs://sample-data-bucket/OCR/scanned_document.jpg}"
ENABLE_PREPROCESSING="${ENABLE_PREPROCESSING:-true}"
ENABLE_LLM="${ENABLE_LLM:-false}"
RETURN_FORMAT="${RETURN_FORMAT:-minimal}"
QUALITY_THRESHOLD="${QUALITY_THRESHOLD:-60}"
CONFIDENCE_THRESHOLD="${CONFIDENCE_THRESHOLD:-80}"
ASYNC_PROCESSING="${ASYNC_PROCESSING:-false}"
VERBOSE="${VERBOSE:-false}"
TEST_MODE="${TEST_MODE:-quick}"  # quick, full, pdf, all

# Help function
show_help() {
    cat << EOF
OCR API Test Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -m, --mode MODE         Test mode: quick, full, pdf, all (default: quick)

    Source Options:
    -f, --file FILE         Test file path (for local testing)
    --obs URL               OBS URL (for OBS testing)
    -s, --source TYPE       Source type: file or obs (default: file)

    API Options:
    -u, --url URL           API URL (default: http://localhost:8000)
    --async                 Enable async processing (default: false)

    Processing Options:
    --preprocessing         Enable preprocessing (default: true)
    --no-preprocessing      Disable preprocessing
    --llm                   Enable LLM enhancement (default: false)
    --no-llm                Disable LLM enhancement
    --format FORMAT         Response format: minimal, ocr_only, full (default: minimal)
    --quality NUM           Quality threshold 0-100 (default: 60)
    --confidence NUM        Confidence threshold 0-100 (default: 80)

    Other:
    -v, --verbose           Verbose output

Examples:
    # Quick test with local file
    $0

    # Test with OBS URL
    $0 --obs obs://bucket/path/to/file.jpg

    # Full pipeline test with all features
    $0 --mode full --llm --format full

    # Test specific PDF from OBS
    $0 --obs obs://bucket/document.pdf --mode pdf

    # Test without preprocessing
    $0 --no-preprocessing --format ocr_only

    # Async processing
    $0 --async --verbose

    # Run all tests
    $0 --mode all --verbose

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -m|--mode)
            TEST_MODE="$2"
            shift 2
            ;;
        -f|--file)
            TEST_FILE="$2"
            SOURCE_TYPE="file"
            shift 2
            ;;
        --obs)
            OBS_URL="$2"
            SOURCE_TYPE="obs"
            shift 2
            ;;
        -s|--source)
            SOURCE_TYPE="$2"
            shift 2
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        --async)
            ASYNC_PROCESSING="true"
            shift
            ;;
        --preprocessing)
            ENABLE_PREPROCESSING="true"
            shift
            ;;
        --no-preprocessing)
            ENABLE_PREPROCESSING="false"
            shift
            ;;
        --llm)
            ENABLE_LLM="true"
            shift
            ;;
        --no-llm)
            ENABLE_LLM="false"
            shift
            ;;
        --format)
            RETURN_FORMAT="$2"
            shift 2
            ;;
        --quality)
            QUALITY_THRESHOLD="$2"
            shift 2
            ;;
        --confidence)
            CONFIDENCE_THRESHOLD="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Functions
log() {
    if [ "$VERBOSE" = "true" ]; then
        echo "$1"
    fi
}

check_api_health() {
    log "Checking API health at $API_URL..."
    if curl -s "$API_URL/health" | grep -q "healthy"; then
        echo "✅ API is healthy"
        return 0
    else
        echo "❌ API is not running at $API_URL"
        echo "   Start it with: python -m src.api.main"
        return 1
    fi
}

encode_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        exit 1
    fi
    log "Encoding file: $file"
    base64 -w 0 "$file"
}

make_request() {
    local request_file="/tmp/ocr_request_$$.json"

    # Create source section based on type
    if [ "$SOURCE_TYPE" = "obs" ]; then
        local source_json='{
            "type": "obs_url",
            "obs_url": "'"$OBS_URL"'"
        }'
        echo "  Source: OBS URL - $OBS_URL"
    else
        local file_base64=$(encode_file "$TEST_FILE")
        local source_json='{
            "type": "file",
            "file": "'"$file_base64"'"
        }'
        echo "  Source: Local file - $TEST_FILE"
    fi

    # Create request JSON
    cat > "$request_file" <<EOF
{
  "source": $source_json,
  "processing_options": {
    "enable_ocr": true,
    "enable_enhancement": ${ENABLE_LLM},
    "enable_preprocessing": ${ENABLE_PREPROCESSING},
    "return_format": "${RETURN_FORMAT}"
  },
  "thresholds": {
    "image_quality_threshold": ${QUALITY_THRESHOLD},
    "confidence_threshold": ${CONFIDENCE_THRESHOLD}
  },
  "async_processing": ${ASYNC_PROCESSING}
}
EOF

    log "Request JSON created at $request_file"
    if [ "$VERBOSE" = "true" ]; then
        echo "Request content:"
        python3 -m json.tool < "$request_file" | head -20
    fi

    log "Sending request to $API_URL/api/v1/ocr..."

    # Send request and measure time
    local start_time=$(date +%s%3N 2>/dev/null || echo "0")
    local response=$(curl -s -X POST "$API_URL/api/v1/ocr" \
        -H "Content-Type: application/json" \
        -d @"$request_file")
    local end_time=$(date +%s%3N 2>/dev/null || echo "0")
    local elapsed=$((end_time - start_time))

    # Clean up
    rm -f "$request_file"

    # Return response and time
    echo "$response"
    if [ "$elapsed" != "0" ]; then
        echo "ELAPSED_TIME:${elapsed}" >&2
    fi
}

handle_async_response() {
    local response="$1"

    # Check if it's an async response
    echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('status') == 'accepted' and 'job_id' in data:
    print(f'Async job submitted: {data[\"job_id\"]}')
    print(f'Estimated time: {data.get(\"estimated_time_seconds\", \"unknown\")} seconds')
    sys.exit(0)
sys.exit(1)
" 2>/dev/null

    if [ $? -eq 0 ]; then
        # Extract job ID
        local job_id=$(echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['job_id'])
" 2>/dev/null)

        echo "Polling for results..."

        # Poll for results (max 60 seconds)
        local max_attempts=30
        local attempt=0

        while [ $attempt -lt $max_attempts ]; do
            sleep 2
            local job_response=$(curl -s "$API_URL/api/v1/ocr/job/$job_id")
11
            local status=$(echo "$job_response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('status', 'unknown'))
" 2>/dev/null)

            log "Job status: $status"

            if [ "$status" = "completed" ]; then
                echo "Job completed!"
                # Return the result
                echo "$job_response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(json.dumps(data.get('result', {})))
" 2>/dev/null
                return 0
            elif [ "$status" = "failed" ]; then
                echo "Job failed!"
                echo "$job_response"
                return 1
            fi

            attempt=$((attempt + 1))
        done

        echo "Timeout waiting for async job"
        return 1
    fi

    # Not an async response, return as-is
    echo "$response"
    return 0
}

parse_response() {
    local response="$1"
    local elapsed="$2"

    # Handle async responses
    if [ "$ASYNC_PROCESSING" = "true" ]; then
        response=$(handle_async_response "$response")
        if [ $? -ne 0 ]; then
            return 1
        fi
    fi

    if [ "$VERBOSE" = "true" ]; then
        echo "Full response:"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    fi

    # Parse and display summary
    echo "$response" | python3 -c "
import json, sys

try:
    data = json.load(sys.stdin)

    # Basic info
    print(f'\\n📋 Results:')
    print(f'  Status: {data.get(\"status\", \"N/A\")}')

    # Document ID
    if 'metadata' in data and data['metadata']:
        print(f'  Document ID: {data[\"metadata\"].get(\"document_id\", \"N/A\")}')
    elif 'document_id' in data:
        print(f'  Document ID: {data.get(\"document_id\", \"N/A\")}')

    # Quality check (if full format)
    if 'quality_check' in data and data['quality_check']:
        print(f'  Quality Score: {data[\"quality_check\"].get(\"score\", 0):.1f}/100')
        print(f'  Quality Passed: {data[\"quality_check\"].get(\"passed\", False)}')

    # OCR results
    if 'ocr_result' in data and data['ocr_result']:
        print(f'  Words Extracted: {data[\"ocr_result\"].get(\"word_count\", 0)}')
        print(f'  OCR Confidence: {data[\"ocr_result\"].get(\"confidence_score\", 0):.1f}%')
    elif 'word_count' in data:  # ocr_only format
        print(f'  Words Extracted: {data.get(\"word_count\", 0)}')
        print(f'  OCR Confidence: {data.get(\"ocr_confidence\", 0):.1f}%')

    # LLM Enhancement
    if 'enhancement' in data and data['enhancement'] and data['enhancement'].get('performed'):
        print(f'  LLM Enhancement: ✅ Performed')
        corrections = data['enhancement'].get('corrections', [])
        print(f'  Corrections Made: {len(corrections)}')

    # Confidence and routing
    if 'confidence_report' in data and data['confidence_report']:
        print(f'  Final Confidence: {data[\"confidence_report\"].get(\"final_confidence\", 0):.1f}%')
        print(f'  Routing: {data[\"confidence_report\"].get(\"routing_decision\", \"N/A\")}')
    elif 'confidence_score' in data:  # minimal format
        print(f'  Final Confidence: {data.get(\"confidence_score\", 0):.1f}%')
        print(f'  Routing: {data.get(\"routing_decision\", \"N/A\")}')

    # Text preview
    text = None
    if 'extracted_text' in data:
        text = data['extracted_text']
    elif 'ocr_result' in data and data['ocr_result']:
        text = data['ocr_result'].get('raw_text')
    elif 'raw_text' in data:
        text = data['raw_text']

    if text:
        preview = text[:100].replace('\\n', ' ') + '...' if len(text) > 100 else text.replace('\\n', ' ')
        print(f'  Text Preview: {preview}')

    # Timing
    if 'metadata' in data and data['metadata'] and 'processing_time_ms' in data['metadata']:
        api_time = data['metadata']['processing_time_ms']
        print(f'  API Processing: {api_time:.0f}ms')
    elif 'processing_time_ms' in data:
        api_time = data['processing_time_ms']
        print(f'  API Processing: {api_time:.0f}ms')

except json.JSONDecodeError as e:
    print(f'❌ Failed to parse JSON response: {e}')
    if '$VERBOSE' == 'true':
        print('Raw response:', data if 'data' in locals() else sys.stdin.read())
except Exception as e:
    print(f'❌ Error: {e}')
" 2>/dev/null || echo "❌ Could not parse response"

    if [ -n "$elapsed" ] && [ "$elapsed" != "0" ]; then
        echo "  Total Request Time: ${elapsed}ms"
    fi
}

run_quick_test() {
    echo "============================================"
    echo "Quick OCR Test"
    echo "============================================"
    echo "Settings:"
    echo "  Source Type: $SOURCE_TYPE"
    if [ "$SOURCE_TYPE" = "obs" ]; then
        echo "  OBS URL: $OBS_URL"
    else
        echo "  File: $TEST_FILE"
    fi
    echo "  Preprocessing: $ENABLE_PREPROCESSING"
    echo "  LLM Enhancement: $ENABLE_LLM"
    echo "  Response Format: $RETURN_FORMAT"
    echo "  Quality Threshold: $QUALITY_THRESHOLD"
    echo "  Confidence Threshold: $CONFIDENCE_THRESHOLD"
    echo "  Async Processing: $ASYNC_PROCESSING"

    local response=$(make_request 2>/tmp/elapsed_$$)
    local elapsed=$(grep "ELAPSED_TIME:" /tmp/elapsed_$$ 2>/dev/null | cut -d: -f2)
    rm -f /tmp/elapsed_$$

    parse_response "$response" "$elapsed"
}

run_full_test() {
    echo "============================================"
    echo "Full Pipeline Test Suite"
    echo "============================================"

    # Test 1: No preprocessing, no LLM
    echo ""
    echo "Test 1: Basic OCR (No Preprocessing, No LLM)"
    echo "--------------------------------------------"
    ENABLE_PREPROCESSING=false ENABLE_LLM=false RETURN_FORMAT=minimal run_quick_test

    # Test 2: With preprocessing, no LLM
    echo ""
    echo "Test 2: OCR with Preprocessing"
    echo "--------------------------------------------"
    ENABLE_PREPROCESSING=true ENABLE_LLM=false RETURN_FORMAT=ocr_only run_quick_test

    # Test 3: Full pipeline
    echo ""
    echo "Test 3: Complete Pipeline"
    echo "--------------------------------------------"
    ENABLE_PREPROCESSING=true ENABLE_LLM="${ENABLE_LLM}" RETURN_FORMAT=full run_quick_test

    # Test 4: OBS if configured
    if [ "$SOURCE_TYPE" = "obs" ] || [ -n "$OBS_URL" ]; then
        echo ""
        echo "Test 4: OBS Processing"
        echo "--------------------------------------------"
        SOURCE_TYPE=obs run_quick_test
    fi
}

run_pdf_test() {
    echo "============================================"
    echo "PDF Processing Test"
    echo "============================================"

    if [ "$SOURCE_TYPE" = "obs" ]; then
        # Use OBS PDF if URL ends with .pdf
        if [[ "$OBS_URL" != *.pdf ]]; then
            OBS_URL="obs://sample-data-bucket/OCR/document.pdf"
        fi
        echo "Testing PDF from OBS: $OBS_URL"
    else
        local pdf_file="${TEST_FILE}"
        if [[ ! "$pdf_file" == *.pdf ]]; then
            pdf_file="tests/documents/scanned_document.pdf"
        fi

        if [ ! -f "$pdf_file" ]; then
            echo "❌ PDF file not found: $pdf_file"
            return 1
        fi
        TEST_FILE="$pdf_file"
        echo "Testing PDF from local: $pdf_file"
    fi

    run_quick_test
}

run_all_tests() {
    echo "============================================"
    echo "Running All Tests"
    echo "============================================"

    # Test with local file
    echo "LOCAL FILE TESTS"
    echo "================"
    SOURCE_TYPE=file run_quick_test

    echo ""
    # Test with OBS if available
    echo "OBS URL TESTS"
    echo "============="
    SOURCE_TYPE=obs run_quick_test

    echo ""
    # Test PDF
    run_pdf_test

    echo ""
    # Test format detection
    echo "Format Detection Test"
    echo "--------------------------------------------"
    local formats_response=$(curl -s "$API_URL/api/v1/ocr/supported-formats")
    echo "$formats_response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Supported Formats: {data.get(\"total_formats\", 0)}')
print(f'Formats: {\" \".join(data.get(\"supported_formats\", []))}')
" 2>/dev/null || echo "Format endpoint not available"

    # Test async if enabled
    if [ "$ASYNC_PROCESSING" = "true" ]; then
        echo ""
        echo "Async Processing Test"
        echo "--------------------------------------------"
        ASYNC_PROCESSING=true run_quick_test
    fi
}

# Main execution
main() {
    # Check API health first
    check_api_health || exit 1

    # Run appropriate test mode
    case "$TEST_MODE" in
        quick)
            run_quick_test
            ;;
        full)
            run_full_test
            ;;
        pdf)
            run_pdf_test
            ;;
        all)
            run_all_tests
            ;;
        *)
            echo "❌ Invalid mode: $TEST_MODE"
            show_help
            exit 1
            ;;
    esac

    echo ""
    echo "✅ Test completed!"
}

# Run main function
main
"""
Streamlit Demo for OCR Document Processing System
"""

import streamlit as st
import requests
import json
import base64
import time
from pathlib import Path
import pandas as pd
from datetime import datetime
import io
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration - can be overridden by environment variable
API_BASE_URL = os.getenv("OCR_API_URL", "http://188.239.9.105:8000")

# Page configuration
st.set_page_config(
    page_title="OCR Document Processing Demo",
    page_icon="📄",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        return response.status_code == 200
    except:
        return False


def encode_file_to_base64(file_content):
    """Encode file content to base64"""
    return base64.b64encode(file_content).decode('utf-8')


def main():
    # Title and description
    st.title("🔍 OCR Document Processing System")
    st.markdown("**Unified AI-Powered Document Analysis with Quality Assessment and LLM Enhancement**")

    # Initialize session state for logs
    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    def add_log(level, message, detail=None):
        """Add a log entry"""
        log_entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "detail": detail
        }
        st.session_state["logs"].append(log_entry)
        # Keep only last 50 logs
        if len(st.session_state["logs"]) > 50:
            st.session_state["logs"] = st.session_state["logs"][-50:]

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Health Check
        if check_api_health():
            st.success("✅ API Connected")
        else:
            st.error("❌ API Offline - Start the API server first")
            st.code("python -m uvicorn src.api.main:app --reload", language="bash")

        st.divider()

        # Processing Configuration
        st.subheader("Processing Settings")

        # OCR Processing
        enable_ocr = st.checkbox("Enable OCR Processing", value=True,
            help="Perform OCR extraction (automatically skipped if quality is below threshold)")

        # Enhancement
        enable_enhancement = st.checkbox("Enable LLM Enhancement", value=False,
            help="Applies comprehensive enhancement including context, spelling, grammar, and structure in a single optimized LLM call")

        st.divider()

        # Thresholds
        st.subheader("Thresholds")

        image_quality_threshold = st.slider(
            "Image Quality Threshold",
            min_value=0,
            max_value=100,
            value=60,  # Updated default
            step=5,
            help="Minimum quality score to proceed with OCR (default: 60)"
        )

        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=0,
            max_value=100,
            value=80,  # Default
            step=5,
            help="Minimum confidence for automatic routing (default: 80)"
        )

        st.divider()

        # Response Format
        st.subheader("Response Format")
        return_format = st.selectbox(
            "Select Format",
            ["full", "minimal", "ocr_only"],
            help="Choose the response format"
        )

        # Async Processing
        async_processing = st.checkbox("Async Processing", value=False,
            help="Process document asynchronously")

        st.divider()

        # Info Section
        st.info("""
        **How it works:**
        - Flexible configuration options
        - Quality check always performed
        - OCR skipped if quality too low
        - Optional LLM enhancement
        - Dual threshold system
        """)

    # Main Content
    tabs = st.tabs(["📤 Upload & Process", "📊 Results", "🔍 Raw Response", "📈 Analytics", "📋 Logs"])

    # Upload & Process Tab
    with tabs[0]:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.header("Document Upload")

            # File upload or OBS URL
            upload_method = st.radio("Select Input Method", ["File Upload", "OBS URL"])

            document_file = None
            obs_url = None

            if upload_method == "File Upload":
                document_file = st.file_uploader(
                    "Choose a document",
                    type=["jpg", "jpeg", "png", "pdf"],
                    help="Upload a document for processing"
                )

                if document_file:
                    st.success(f"📄 File loaded: {document_file.name}")
                    # Show preview for images
                    if document_file.type.startswith("image/"):
                        st.image(document_file, caption="Document Preview", use_column_width=True)

            else:
                obs_url = st.text_input(
                    "OBS URL",
                    placeholder="obs://bucket-name/path/to/document.jpg",
                    help="Enter the OBS URL of your document"
                )

            # Process button
            if st.button("🚀 Process Document", type="primary", use_container_width=True):
                if not (document_file or obs_url):
                    st.error("Please upload a file or provide an OBS URL")
                else:
                    with st.spinner("Processing document..."):
                        try:
                            add_log("INFO", "Starting document processing")

                            # Prepare request payload
                            request_data = {
                                "processing_options": {
                                    "enable_ocr": enable_ocr,
                                    "enable_enhancement": enable_enhancement,
                                    "return_format": return_format
                                },
                                "thresholds": {
                                    "image_quality_threshold": image_quality_threshold,
                                    "confidence_threshold": confidence_threshold
                                },
                                "async_processing": async_processing
                            }

                            # Add source based on input method
                            if document_file:
                                file_content = document_file.read()
                                add_log("INFO", f"Encoding file: {document_file.name} ({len(file_content)} bytes)")
                                request_data["source"] = {
                                    "type": "file",
                                    "file": encode_file_to_base64(file_content)
                                }
                            else:
                                add_log("INFO", f"Using OBS URL: {obs_url}")
                                request_data["source"] = {
                                    "type": "obs_url",
                                    "obs_url": obs_url
                                }

                            # Make API request
                            add_log("INFO", f"Sending request to API: {API_BASE_URL}/api/v1/ocr")
                            add_log("DEBUG", "Request options", {"enable_ocr": enable_ocr, "enable_enhancement": enable_enhancement, "format": return_format})
                            start_time = time.time()
                            response = requests.post(
                                f"{API_BASE_URL}/api/v1/ocr",
                                json=request_data,
                                headers={"Content-Type": "application/json"}
                            )
                            elapsed_time = time.time() - start_time
                            add_log("INFO", f"API response received: {response.status_code} in {elapsed_time:.2f}s")

                            if response.status_code == 200:
                                result = response.json()
                                st.session_state["result"] = result
                                st.session_state["processing_time"] = elapsed_time

                                if async_processing and "job_id" in result:
                                    # Handle async response
                                    st.success(f"✅ Job submitted: {result['job_id']}")
                                    st.info(f"Estimated time: {result.get('estimated_time_seconds', 30)} seconds")

                                    # Poll for results
                                    if st.button("Check Job Status"):
                                        job_response = requests.get(
                                            f"{API_BASE_URL}/api/v1/ocr/job/{result['job_id']}"
                                        )
                                        if job_response.status_code == 200:
                                            job_result = job_response.json()
                                            st.json(job_result)
                                else:
                                    # Handle sync response
                                    add_log("SUCCESS", f"Processing complete in {elapsed_time:.2f} seconds")
                                    st.success(f"✅ Processing complete in {elapsed_time:.2f} seconds!")

                                    # Display key metrics
                                    if result.get("status") == "success":
                                        col1, col2, col3, col4 = st.columns(4)

                                        with col1:
                                            if "quality_check" in result and result["quality_check"]:
                                                quality_score = result["quality_check"].get("score", 0)
                                                st.metric("Quality Score", f"{quality_score:.1f}")

                                        with col2:
                                            if "ocr_result" in result and result["ocr_result"]:
                                                word_count = result["ocr_result"].get("word_count", 0)
                                                st.metric("Words Extracted", word_count)

                                        with col3:
                                            if "confidence_report" in result:
                                                confidence = result["confidence_report"].get("final_confidence", 0)
                                                st.metric("Confidence", f"{confidence:.1f}%")

                                        with col4:
                                            if "confidence_report" in result:
                                                routing = result["confidence_report"].get("routing_decision", "unknown")
                                                st.metric("Routing", routing)
                                    else:
                                        error_msg = result.get('error', 'Unknown error')
                                        add_log("ERROR", f"Processing failed: {error_msg}")
                                        st.error(f"Processing failed: {error_msg}")

                            else:
                                add_log("ERROR", f"API Error {response.status_code}", response.text)
                                st.error(f"API Error ({response.status_code}): {response.text}")

                        except requests.exceptions.RequestException as e:
                            add_log("ERROR", f"Request failed: {str(e)}")
                            st.error(f"Request failed: {str(e)}")
                        except Exception as e:
                            add_log("ERROR", f"Error processing document: {str(e)}")
                            st.error(f"Error processing document: {str(e)}")

        with col2:
            st.header("Quick Info")

            if "result" in st.session_state and st.session_state["result"].get("status") == "success":
                result = st.session_state["result"]

                # Quality Check Results
                if "quality_check" in result and result["quality_check"]:
                    st.subheader("📷 Quality Check")
                    qc = result["quality_check"]

                    if qc.get("passed"):
                        st.success(f"✅ Passed (Score: {qc.get('score', 0):.1f})")
                    else:
                        st.error(f"❌ Failed (Score: {qc.get('score', 0):.1f})")

                    # Show metrics
                    if "metrics" in qc:
                        for metric, value in qc["metrics"].items():
                            st.progress(value / 100)
                            st.caption(f"{metric}: {value:.1f}")

                st.divider()

                # Confidence Report
                if "confidence_report" in result:
                    st.subheader("🎯 Confidence Report")
                    cr = result["confidence_report"]

                    # Show scores
                    st.metric("Image Quality", f"{cr.get('image_quality_score', 0):.1f}")
                    st.metric("OCR Confidence", f"{cr.get('ocr_confidence_score', 0):.1f}")
                    st.metric("**Final Confidence**", f"{cr.get('final_confidence', 0):.1f}%")

                    # Routing decision
                    routing = cr.get("routing_decision", "unknown")
                    if routing == "pass":
                        st.success(f"✅ {cr.get('routing_reason', 'Automatic processing')}")
                    else:
                        st.warning(f"⚠️ {cr.get('routing_reason', 'Manual review required')}")

    # Results Tab
    with tabs[1]:
        st.header("Processing Results")

        if "result" in st.session_state and st.session_state["result"].get("status") == "success":
            result = st.session_state["result"]

            # Create columns for different aspects
            result_tabs = st.tabs(["📝 Text", "✨ Enhancement", "📊 Confidence", "⏱️ Performance"])

            with result_tabs[0]:
                st.subheader("Extracted Text")

                if "ocr_result" in result and result["ocr_result"]:
                    ocr = result["ocr_result"]

                    # Text display
                    st.text_area(
                        "OCR Text",
                        ocr.get("raw_text", "No text extracted"),
                        height=400,
                        key="extracted_text"
                    )

                    # Confidence distribution
                    if "confidence_distribution" in ocr:
                        st.subheader("Confidence Distribution")
                        dist = ocr["confidence_distribution"]
                        df = pd.DataFrame([dist])
                        st.bar_chart(df.T)
                else:
                    st.info("No OCR results available (quality check may have failed)")

            with result_tabs[1]:
                st.subheader("LLM Enhancement")

                if "enhancement" in result and result["enhancement"] and result["enhancement"].get("performed"):
                    enh = result["enhancement"]

                    # Enhanced text
                    st.text_area(
                        "Enhanced Text",
                        enh.get("enhanced_text", "No enhanced text"),
                        height=400,
                        key="enhanced_text"
                    )

                    # Corrections
                    if "corrections" in enh and enh["corrections"]:
                        st.subheader("Corrections Made")
                        df = pd.DataFrame(enh["corrections"])
                        st.dataframe(df, use_container_width=True)

                    # Stats
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Processing Time", f"{enh.get('processing_time_ms', 0)/1000:.2f}s")
                    with col2:
                        st.metric("Tokens Used", enh.get("tokens_used", 0))
                else:
                    st.info("Enhancement not performed or not enabled")

            with result_tabs[2]:
                st.subheader("Confidence Analysis")

                if "confidence_report" in result:
                    cr = result["confidence_report"]

                    # Create a visual representation
                    scores_data = {
                        "Component": ["Image Quality", "OCR Confidence", "Final Score"],
                        "Score": [
                            cr.get("image_quality_score", 0),
                            cr.get("ocr_confidence_score", 0),
                            cr.get("final_confidence", 0)
                        ]
                    }
                    df = pd.DataFrame(scores_data)
                    st.bar_chart(df.set_index("Component"))

                    # Threshold comparison
                    st.subheader("Threshold Analysis")
                    thresholds = cr.get("thresholds_applied", {})

                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"Image Quality Threshold: {thresholds.get('image_quality_threshold', 60)}")
                        if cr.get("quality_check_passed"):
                            st.success("✅ Quality check passed")
                        else:
                            st.error("❌ Quality check failed")

                    with col2:
                        st.info(f"Confidence Threshold: {thresholds.get('confidence_threshold', 80)}")
                        if cr.get("confidence_check_passed"):
                            st.success("✅ Confidence check passed")
                        else:
                            st.error("❌ Confidence check failed")

            with result_tabs[3]:
                st.subheader("Performance Metrics")

                if "metadata" in result:
                    meta = result["metadata"]

                    # Overall processing time
                    st.metric("Total Processing Time", f"{meta.get('processing_time_ms', 0)/1000:.2f}s")

                    # Breakdown
                    st.subheader("Processing Breakdown")

                    breakdown = []

                    if "quality_check" in result and result["quality_check"]:
                        if "processing_time_ms" in result["quality_check"]:
                            breakdown.append({
                                "Stage": "Quality Check",
                                "Time (ms)": result["quality_check"]["processing_time_ms"]
                            })

                    if "ocr_result" in result and result["ocr_result"]:
                        if "processing_time_ms" in result["ocr_result"]:
                            breakdown.append({
                                "Stage": "OCR Processing",
                                "Time (ms)": result["ocr_result"]["processing_time_ms"]
                            })

                    if "enhancement" in result and result["enhancement"]:
                        if "processing_time_ms" in result["enhancement"]:
                            breakdown.append({
                                "Stage": "LLM Enhancement",
                                "Time (ms)": result["enhancement"]["processing_time_ms"]
                            })

                    if breakdown:
                        df = pd.DataFrame(breakdown)
                        st.dataframe(df, use_container_width=True)

                        # Visualization
                        st.bar_chart(df.set_index("Stage"))

        elif "result" in st.session_state:
            result = st.session_state["result"]
            if result.get("status") == "failed":
                st.error(f"Processing failed: {result.get('error', 'Unknown error')}")
            elif result.get("status") == "processing":
                st.info("Document is still processing...")
        else:
            st.info("No results available. Process a document first.")

    # Raw Response Tab
    with tabs[2]:
        st.header("Raw API Response")

        if "result" in st.session_state:
            # Pretty print JSON
            st.json(st.session_state["result"])

            # Download button
            result_json = json.dumps(st.session_state["result"], indent=2)
            st.download_button(
                label="📥 Download Response (JSON)",
                data=result_json,
                file_name=f"ocr_response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

            # Processing time
            if "processing_time" in st.session_state:
                st.metric("API Response Time", f"{st.session_state['processing_time']:.2f}s")
        else:
            st.info("No response data available")

    # Analytics Tab
    with tabs[3]:
        st.header("Processing Analytics")

        if "result" in st.session_state and st.session_state["result"].get("status") == "success":
            result = st.session_state["result"]

            # Create summary statistics
            col1, col2, col3 = st.columns(3)

            with col1:
                st.subheader("Document Stats")
                if "ocr_result" in result and result["ocr_result"]:
                    st.metric("Words", result["ocr_result"].get("word_count", 0))
                    st.metric("Characters", len(result["ocr_result"].get("raw_text", "")))

            with col2:
                st.subheader("Quality Metrics")
                if "quality_check" in result and result["quality_check"]:
                    qc = result["quality_check"]
                    st.metric("Quality Score", f"{qc.get('score', 0):.1f}")
                    st.metric("Issues Found", len(qc.get("issues", [])))

            with col3:
                st.subheader("Processing Efficiency")
                if "metadata" in result:
                    total_time = result["metadata"].get("processing_time_ms", 0) / 1000
                    st.metric("Total Time", f"{total_time:.2f}s")

                    # Calculate efficiency
                    if "ocr_result" in result and result["ocr_result"]:
                        words = result["ocr_result"].get("word_count", 1)
                        if words > 0:
                            st.metric("Words/Second", f"{words/total_time:.0f}")

            # Comparison with thresholds
            st.divider()
            st.subheader("Threshold Compliance")

            if "confidence_report" in result:
                cr = result["confidence_report"]

                # Create comparison chart
                threshold_data = {
                    "Metric": ["Image Quality", "Confidence"],
                    "Actual": [
                        cr.get("image_quality_score", 0),
                        cr.get("final_confidence", 0)
                    ],
                    "Threshold": [
                        cr.get("thresholds_applied", {}).get("image_quality_threshold", 60),
                        cr.get("thresholds_applied", {}).get("confidence_threshold", 80)
                    ]
                }

                df = pd.DataFrame(threshold_data)
                st.bar_chart(df.set_index("Metric"))
        else:
            st.info("Process a document to see analytics")

    # Logs Tab
    with tabs[4]:
        st.header("System Logs")

        # Log controls
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("🗑️ Clear Logs"):
                st.session_state["logs"] = []
                add_log("INFO", "Logs cleared")
                st.rerun()

        with col2:
            log_level_filter = st.selectbox(
                "Filter Level",
                ["All", "ERROR", "WARNING", "INFO", "SUCCESS", "DEBUG"],
                key="log_filter"
            )

        with col3:
            auto_scroll = st.checkbox("Auto-scroll", value=True)

        # Display logs
        if st.session_state["logs"]:
            # Filter logs if needed
            filtered_logs = st.session_state["logs"]
            if log_level_filter != "All":
                filtered_logs = [log for log in filtered_logs if log["level"] == log_level_filter]

            # Create log display
            log_container = st.container()
            with log_container:
                for log in reversed(filtered_logs):  # Show newest first
                    # Choose color based on level
                    if log["level"] == "ERROR":
                        color = "🔴"
                    elif log["level"] == "WARNING":
                        color = "🟡"
                    elif log["level"] == "SUCCESS":
                        color = "🟢"
                    elif log["level"] == "DEBUG":
                        color = "🔵"
                    else:
                        color = "⚪"

                    # Format log entry
                    log_text = f"{color} **[{log['time']}] {log['level']}:** {log['message']}"

                    # Add detail if present
                    if log.get("detail"):
                        with st.expander(log_text, expanded=False):
                            if isinstance(log["detail"], dict):
                                st.json(log["detail"])
                            else:
                                st.code(str(log["detail"]), language="text")
                    else:
                        st.markdown(log_text)

            # Show log count
            st.caption(f"Showing {len(filtered_logs)} of {len(st.session_state['logs'])} logs")
        else:
            st.info("No logs available. Process a document to see logs.")


if __name__ == "__main__":
    main()
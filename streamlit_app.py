"""
Streamlit Demo for OCR Document Processing System
"""

import streamlit as st
import requests
import json
import time
from pathlib import Path
import pandas as pd
from datetime import datetime
import io

# API Configuration
API_BASE_URL = "http://localhost:8000"

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
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Check if API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        return response.status_code == 200
    except:
        return False


def main():
    # Title and description
    st.title("🔍 OCR Document Processing System")
    st.markdown("**AI-Powered Document Analysis with Quality Assessment and LLM Enhancement**")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")

        # API Health Check
        if check_api_health():
            st.success("✅ API Connected")
        else:
            st.error("❌ API Offline - Start the API server first")
            st.code("python -m src.api.main", language="bash")

        st.divider()

        # Processing Configuration
        st.subheader("Processing Settings")

        quality_threshold = st.slider(
            "Image Quality Threshold",
            min_value=10,
            max_value=90,
            value=30,
            step=10,
            help="Minimum quality score to proceed with OCR"
        )

        confidence_threshold = st.slider(
            "Confidence Threshold",
            min_value=50,
            max_value=95,
            value=80,
            step=5,
            help="Minimum confidence for automatic processing"
        )

        st.divider()

        # Enhancement Options
        st.subheader("LLM Enhancement")

        enable_enhancement = st.checkbox("Enable LLM Enhancement", value=True,
            help="Performs comprehensive enhancement including grammar, context, and structure analysis in a single optimized call")

        st.divider()

        # Info Section
        st.info("""
        **Pipeline Steps:**
        1. Image Quality Check
        2. OCR Processing
        3. LLM Enhancement (optional)
        4. Confidence Scoring
        5. Routing Decision
        """)

    # Main Content
    tabs = st.tabs(["📤 Upload & Process", "📊 Results", "📈 Analytics", "💰 Cost Estimation"])

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

            else:
                obs_url = st.text_input(
                    "OBS URL",
                    placeholder="obs://bucket-name/document.jpg",
                    help="Enter the OBS URL of your document"
                )

            # Process button
            if st.button("🚀 Process Document", type="primary", use_container_width=True):
                if not (document_file or obs_url):
                    st.error("Please upload a file or provide an OBS URL")
                else:
                    with st.spinner("Processing document..."):
                        # Prepare request
                        files = None
                        data = {
                            "quality_threshold": quality_threshold,
                            "confidence_threshold": confidence_threshold,
                            "enable_context": enable_enhancement  # Using context as the flag for enhancement
                        }

                        if document_file:
                            files = {"file": document_file}
                        else:
                            data["obs_url"] = obs_url

                        try:
                            # Submit document
                            response = requests.post(
                                f"{API_BASE_URL}/documents/process",
                                files=files,
                                data=data
                            )

                            if response.status_code == 200:
                                result = response.json()
                                st.session_state["document_id"] = result["document_id"]
                                st.success(f"✅ Document submitted: {result['document_id']}")

                                # Wait for processing
                                progress_bar = st.progress(0)
                                status_text = st.empty()

                                for i in range(100):
                                    # Check status
                                    status_response = requests.get(
                                        f"{API_BASE_URL}/documents/{result['document_id']}/status"
                                    )

                                    if status_response.status_code == 200:
                                        status_data = status_response.json()

                                        if status_data["status"] in ["completed", "manual_review", "failed"]:
                                            progress_bar.progress(100)
                                            break

                                        status_text.text(f"Status: {status_data['status']}")
                                        progress_bar.progress(min(i + 10, 90))

                                    time.sleep(1)

                                # Get final result
                                final_response = requests.get(
                                    f"{API_BASE_URL}/documents/{result['document_id']}/result"
                                )

                                if final_response.status_code == 200:
                                    final_result = final_response.json()
                                    st.session_state["result"] = final_result
                                    st.success("✅ Processing complete!")

                                    # Display key metrics
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Words Extracted", final_result.get("word_count", 0))
                                    with col2:
                                        st.metric("Status", final_result.get("status", "Unknown"))
                                    with col3:
                                        processing_time = final_result.get("processing_metrics", {}).get("total_processing_time", 0)
                                        st.metric("Processing Time", f"{processing_time:.1f}s")

                                else:
                                    st.error("Failed to get processing results")

                            else:
                                st.error(f"Error: {response.text}")

                        except Exception as e:
                            st.error(f"Error processing document: {str(e)}")

        with col2:
            st.header("Quick Stats")

            # Display session stats
            if "result" in st.session_state:
                result = st.session_state["result"]

                # Confidence scores
                if "document_id" in st.session_state:
                    conf_response = requests.get(
                        f"{API_BASE_URL}/documents/{st.session_state['document_id']}/confidence"
                    )

                    if conf_response.status_code == 200:
                        conf_data = conf_response.json()

                        st.subheader("Confidence Scores")
                        scores = conf_data.get("confidence_scores", {})

                        # Only show active scores (Image Quality and OCR)
                        active_scores = {
                            "image_quality": scores.get("image_quality", 0),
                            "ocr_confidence": scores.get("ocr_confidence", 0),
                            "final": scores.get("final", 0)
                        }

                        for key, value in active_scores.items():
                            if key == "final":
                                st.metric(f"**{key.replace('_', ' ').title()}**", f"{value:.1f}%")
                            else:
                                st.progress(value / 100)
                                st.caption(f"{key.replace('_', ' ').title()}: {value:.1f}%")

                        # Routing decision
                        routing = conf_data.get("routing", {})
                        if routing.get("decision") == "automatic":
                            st.success("✅ Automatic Processing")
                        else:
                            st.warning("⚠️ Manual Review Required")

    # Results Tab
    with tabs[1]:
        st.header("Processing Results")

        if "result" in st.session_state:
            result = st.session_state["result"]

            # Add download button at the top
            col1, col2, col3 = st.columns([2, 1, 1])
            with col3:
                # Create full report
                report = create_full_report(result, st.session_state.get("document_id", ""))
                report_json = json.dumps(report, indent=2)

                st.download_button(
                    label="📥 Download Full Report (JSON)",
                    data=report_json,
                    file_name=f"ocr_report_{st.session_state.get('document_id', 'unknown')[:8]}.json",
                    mime="application/json",
                    use_container_width=True
                )

            # Create tabs for different result views
            result_tabs = st.tabs(["Extracted Text", "Enhanced Text", "Corrections", "Metrics"])

            with result_tabs[0]:
                st.subheader("Original OCR Text")
                extracted_text = result.get("extracted_text", "")
                st.text_area("Text", extracted_text, height=400, key="extracted", label_visibility="collapsed")

            with result_tabs[1]:
                st.subheader("Enhanced Text (LLM Corrected)")
                enhanced_text = result.get("enhanced_text", "")
                if enhanced_text:
                    st.text_area("Text", enhanced_text, height=400, key="enhanced", label_visibility="collapsed")
                else:
                    st.info("No enhancements applied or available")

            with result_tabs[2]:
                st.subheader("Corrections Made")
                corrections = result.get("corrections_made", [])
                if corrections:
                    df = pd.DataFrame(corrections)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No corrections made")

            with result_tabs[3]:
                st.subheader("Processing Metrics")
                metrics = result.get("processing_metrics", {})
                if metrics:
                    st.json(metrics)

        else:
            st.info("No results available. Process a document first.")

    # Analytics Tab
    with tabs[2]:
        st.header("System Analytics")

        # Get queue statistics
        try:
            stats_response = requests.get(f"{API_BASE_URL}/queue/stats")
            if stats_response.status_code == 200:
                stats = stats_response.json()

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Documents", stats.get("total_documents", 0))
                with col2:
                    st.metric("Completed", stats.get("completed", 0))
                with col3:
                    st.metric("Manual Review", stats.get("manual_review", 0))
                with col4:
                    st.metric("Failed", stats.get("failed", 0))

                # Priority distribution
                st.subheader("Priority Distribution")
                priority_dist = stats.get("priority_distribution", {})
                if priority_dist:
                    df = pd.DataFrame([priority_dist])
                    st.bar_chart(df.T)

        except Exception as e:
            st.error(f"Failed to load analytics: {str(e)}")

    # Cost Estimation Tab
    with tabs[3]:
        st.header("Cost Estimation")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Estimate Processing Costs")

            doc_size = st.number_input("Document Size (MB)", min_value=0.1, max_value=10.0, value=2.0)
            num_docs = st.number_input("Number of Documents", min_value=1, max_value=1000, value=10)

            enable_llm = st.checkbox("Include LLM Enhancement", value=True)
            enhancement_options = ["context"] if enable_llm else []

            if st.button("Calculate Cost"):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/cost/estimate",
                        json={
                            "document_size_mb": doc_size,
                            "enhancement_types": enhancement_options,
                            "num_documents": num_docs
                        }
                    )

                    if response.status_code == 200:
                        estimate = response.json()

                        st.success("Cost Estimate Generated")

                        # Display costs
                        st.metric("Total Cost", f"${estimate['total']['estimated_total_cost']}")
                        st.metric("Processing Time", f"{estimate['processing_time']['total_seconds']:.0f}s")

                        # Breakdown
                        st.json(estimate)

                except Exception as e:
                    st.error(f"Failed to estimate cost: {str(e)}")

        with col2:
            st.subheader("Pricing Information")

            try:
                pricing_response = requests.get(f"{API_BASE_URL}/cost/pricing")
                if pricing_response.status_code == 200:
                    pricing = pricing_response.json()
                    st.json(pricing)
            except:
                st.info("Pricing information unavailable")


def create_full_report(result, document_id):
    """Create a comprehensive report from processing results"""
    report = {
        "document_id": document_id,
        "timestamp": datetime.now().isoformat(),
        "status": result.get("status", "unknown"),
        "processing_metrics": result.get("processing_metrics", {}),
        "confidence_report": result.get("confidence_report", {}),
        "extracted_text": result.get("extracted_text", ""),
        "enhanced_text": result.get("enhanced_text", ""),
        "corrections_made": result.get("corrections_made", []),
        "word_count": len(result.get("extracted_text", "").split()),
        "enhancement_applied": bool(result.get("enhanced_text", ""))
    }

    # Add confidence scores if available
    if document_id:
        try:
            conf_response = requests.get(f"{API_BASE_URL}/documents/{document_id}/confidence")
            if conf_response.status_code == 200:
                conf_data = conf_response.json()
                report["confidence_scores"] = conf_data.get("confidence_scores", {})
                report["routing_decision"] = conf_data.get("routing", {})
        except:
            pass

    return report


if __name__ == "__main__":
    main()
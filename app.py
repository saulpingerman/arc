#!/usr/bin/env python3
"""
ARC (AI Resume Critique)
Streamlit Web Interface for AI-powered resume evaluation.

This is the main entry point for the application.
Run with: streamlit run app.py
"""

import streamlit as st

from arc.config import APP_NAME, APP_FULL_NAME, get_active_config
from arc.evaluation import analyze_job_posting
from arc.processing import process_candidates
from arc.excel_output import create_output_file
from arc.ui import inject_styles, render_sidebar, render_main_content

# Import LLM client from the existing llm_clients module
from llm_clients import create_llm_client, LLMConfig, LLMBackend


def get_llm_client():
    """Create the LLM client using active configuration."""
    config = get_active_config()

    # Map config backend_type string to LLMBackend enum
    backend_map = {
        "AWS_BEDROCK": LLMBackend.AWS_BEDROCK,
        "AWS_GOVCLOUD": LLMBackend.AWS_GOVCLOUD,
        "ANTHROPIC_DIRECT": LLMBackend.ANTHROPIC_DIRECT
    }

    llm_config = LLMConfig(
        backend=backend_map[config.backend_type],
        model_id=config.model_id,
        aws_region=config.region
    )
    return create_llm_client(llm_config)


def main():
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title=f"{APP_NAME} - {APP_FULL_NAME}",
        page_icon=":",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Inject custom styles
    inject_styles()

    # Render sidebar and get configuration
    sidebar_config = render_sidebar(
        get_llm_client=get_llm_client,
        analyze_job_posting=analyze_job_posting
    )

    # Store test count in session state for main content to use
    if sidebar_config['test_mode']:
        st.session_state.test_count = sidebar_config['test_count']
    else:
        st.session_state.test_count = None

    # Render main content
    render_main_content(
        process_candidates=process_candidates,
        create_output_file=create_output_file,
        get_llm_client=get_llm_client,
        config=get_active_config()
    )


if __name__ == "__main__":
    main()

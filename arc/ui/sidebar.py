"""
Sidebar UI Component for ARC Streamlit Application.
"""

import streamlit as st
from typing import Optional, Callable

from ..config import (
    APP_NAME, APP_FULL_NAME, APP_VERSION,
    AUTHOR_NAME, AUTHOR_EMAIL, FEATURES,
    DEFAULT_WEIGHTS, DEFAULT_STRICTNESS
)


def render_sidebar(get_llm_client: Callable, analyze_job_posting: Callable) -> dict:
    """Render the sidebar and return configuration settings.

    Args:
        get_llm_client: Function to create LLM client
        analyze_job_posting: Function to analyze job postings

    Returns:
        Dict with sidebar configuration (test_mode, test_count)
    """
    with st.sidebar:
        # Header
        st.markdown(
            f'<div style="text-align: center; width: 100%; margin-top: -3rem;">'
            f'<div style="font-size: 4rem; font-weight: 900; color: #1f77b4; letter-spacing: 0.3rem;">{APP_NAME}</div>'
            f'<div style="font-size: 0.9rem; color: #666; margin-top: -1.5rem; margin-bottom: 2rem;">{APP_FULL_NAME}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Author info (if configured)
        if FEATURES.get('show_author_info', False) and AUTHOR_NAME:
            st.markdown(f'<div style="margin-top: -0.5rem;">Created by: {AUTHOR_NAME}</div>', unsafe_allow_html=True)
            if AUTHOR_EMAIL:
                st.markdown(f'<div style="margin-top: -0.5rem; margin-bottom: 0.75rem;">Contact: <a href="mailto:{AUTHOR_EMAIL}">{AUTHOR_EMAIL}</a></div>', unsafe_allow_html=True)

        st.divider()

        # Initialize session state
        if 'custom_weights' not in st.session_state:
            st.session_state.custom_weights = None
        if 'job_analysis' not in st.session_state:
            st.session_state.job_analysis = None
        if 'strictness' not in st.session_state:
            st.session_state.strictness = DEFAULT_STRICTNESS
        if 'cached_job_posting_text' not in st.session_state:
            st.session_state.cached_job_posting_text = None

        # Custom Scoring
        _render_scoring_section()

        # Job Analysis
        _render_job_analysis_section(get_llm_client, analyze_job_posting)

        st.divider()

        # Options
        test_mode, test_count = _render_options_section()

        st.divider()

        # Backend info
        _render_backend_info()

        st.divider()

        # About
        st.subheader("About")
        st.caption("This tool uses Claude AI to assist in the evaluation of resumes based on job requirements. Ranks candidates with a score ranging from 1 to 100.")
        st.caption(f"Version {APP_VERSION}")

    return {
        'test_mode': test_mode,
        'test_count': test_count
    }


def _render_scoring_section():
    """Render the custom scoring section."""
    with st.expander("Custom Scoring", expanded=False):
        st.caption("Customize scoring strictness and weights")

        # Strictness
        st.markdown("**Scoring Strictness**")
        st.select_slider(
            "Strictness Level",
            options=["lenient", "balanced", "strict"],
            value=st.session_state.strictness,
            help="Strict mode creates wider score spread to better differentiate exceptional vs average candidates.",
            label_visibility="collapsed",
            key="strictness"
        )

        if st.session_state.strictness == "strict":
            st.info("**Strict**: Exceptional candidates score 85-100, average candidates 50-70")
        elif st.session_state.strictness == "balanced":
            st.info("**Balanced**: Most candidates score 70-85, exceptional 90+")
        else:
            st.info("**Lenient**: Most candidates score 80-90, exceptional 95+")

        st.divider()

        # Weights
        st.markdown("**Scoring Weights**")
        st.caption("Adjust the relative importance of each evaluation category (automatically normalized to 100)")

        required_weight = st.slider(
            "Required Skills",
            min_value=0, max_value=100,
            value=DEFAULT_WEIGHTS['required_skills'],
            step=5, help="Weight for required skills evaluation"
        )

        preferred_weight = st.slider(
            "Preferred Skills",
            min_value=0, max_value=100,
            value=DEFAULT_WEIGHTS['preferred_skills'],
            step=5, help="Weight for preferred skills evaluation"
        )

        education_weight = st.slider(
            "Education",
            min_value=0, max_value=100,
            value=DEFAULT_WEIGHTS['education'],
            step=5, help="Weight for education evaluation"
        )

        total_weight = required_weight + preferred_weight + education_weight

        if total_weight > 0:
            normalized_req = int(round((required_weight / total_weight) * 100))
            normalized_pref = int(round((preferred_weight / total_weight) * 100))
            normalized_edu = 100 - normalized_req - normalized_pref

            st.session_state.custom_weights = {
                'required_skills': normalized_req,
                'preferred_skills': normalized_pref,
                'education': normalized_edu
            }

            if total_weight != 100:
                st.info(f"Normalized weights: Required {normalized_req}%, Preferred {normalized_pref}%, Education {normalized_edu}%")
            else:
                st.success(f"Total weight: {total_weight}")
        else:
            st.warning("All weights are 0. Please set at least one weight greater than 0.")
            st.session_state.custom_weights = None


def _render_job_analysis_section(get_llm_client: Callable, analyze_job_posting: Callable):
    """Render the job analysis section."""
    with st.expander("Analyze Job Posting", expanded=False):
        st.caption("Use AI to analyze the job posting and extract requirements")

        if st.button("Analyze Job Posting", help="Use Claude AI to extract requirements", key="sidebar_analyze_job_btn"):
            if st.session_state.cached_job_posting_text:
                try:
                    client = get_llm_client()
                    with st.spinner("Analyzing job posting..."):
                        analysis = analyze_job_posting(client, st.session_state.cached_job_posting_text)

                    if 'error' not in analysis:
                        st.session_state.job_analysis = analysis
                        st.success("Job posting analyzed successfully!")
                    else:
                        st.error(f"Analysis failed: {analysis['error']}")
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
            else:
                st.warning("Please upload a job posting file first")


def _render_options_section() -> tuple:
    """Render the options section and return test mode settings."""
    st.subheader("Options")

    test_mode = st.checkbox(
        "Test Mode",
        value=False,
        help="Process only a limited number of candidates for testing"
    )

    test_count = None
    if test_mode:
        test_count = st.number_input(
            "Number of candidates to process",
            min_value=1, max_value=100,
            value=3, step=1,
            help="Specify how many candidates to process in test mode"
        )

    return test_mode, test_count


def _render_backend_info():
    """Render the LLM backend information."""
    from ..config import get_active_config

    config = get_active_config()
    st.subheader("LLM Backend")
    st.info(f"**Backend:** AWS Bedrock\n\n**Model:** {config.model_name}\n\n**Region:** {config.region}")

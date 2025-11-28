"""
CSS Styles for ARC Streamlit Application.
"""

import streamlit as st


def inject_styles():
    """Inject custom CSS styles into the Streamlit app."""
    st.markdown("""
<style>
    .sidebar-header {
        font-size: 50rem;
        font-weight: 900;
        color: #1f77b4;
        margin-bottom: 1.5rem;
        margin-top: 0;
        letter-spacing: 0.5rem;
        text-align: center;
    }
    .main-header {
        font-size: 6rem;
        font-weight: 900;
        color: #1f77b4;
        margin-bottom: 0.5rem;
        letter-spacing: 0.2rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
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
    /* Reduce spacing in sidebar */
    section[data-testid="stSidebar"] .stMarkdown {
        margin-bottom: 0rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0.5rem !important;
    }
    section[data-testid="stSidebar"] hr {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }
    section[data-testid="stSidebar"] h2 {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
        padding-top: 0rem !important;
    }
    section[data-testid="stSidebar"] h3 {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
        padding-top: 0rem !important;
    }
    section[data-testid="stSidebar"] .stTextInput > div {
        margin-top: 0rem !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

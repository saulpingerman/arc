"""
Main Content UI Component for ARC Streamlit Application.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from typing import Optional, Callable

from ..config import DEFAULT_WEIGHTS


def render_main_content(process_candidates: Callable,
                        create_output_file: Callable,
                        get_llm_client: Callable,
                        config) -> None:
    """Render the main content area.

    Args:
        process_candidates: Function to process candidates
        create_output_file: Function to create output Excel file
        get_llm_client: Function to create LLM client
        config: Active AWS configuration
    """
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Input Files")

        # Job posting file (REQUIRED)
        job_posting_file = st.file_uploader(
            "Job Posting File (REQUIRED) - .txt or .rtf format",
            type=['txt', 'rtf'],
            help="Text or RTF file containing the job posting description"
        )

        # Cache job posting text when uploaded
        if job_posting_file:
            if 'last_uploaded_file' not in st.session_state or st.session_state.get('last_uploaded_file') != job_posting_file.name:
                st.session_state.cached_job_posting_text = job_posting_file.read().decode('utf-8')
                st.session_state.last_uploaded_file = job_posting_file.name
                job_posting_file.seek(0)

        # Candidates file
        candidates_file = st.file_uploader(
            "Candidates Excel File (.xlsx)",
            type=['xlsx'],
            help="Excel file containing candidate data with 'Resume Text' column"
        )

        # Payband standards file (OPTIONAL)
        payband_standards_file = st.file_uploader(
            "Payband Standards File (OPTIONAL) - .txt or .rtf format",
            type=['txt', 'rtf'],
            help="Text file containing detailed standards/requirements for each payband level"
        )

        # Previous results file (OPTIONAL)
        previous_results_file = st.file_uploader(
            "Previous Results File (OPTIONAL) - .xlsx format",
            type=['xlsx'],
            help="Upload your previous REVIEWED_CANDIDATES.xlsx file to skip already-processed candidates and only evaluate new ones"
        )

    with col2:
        st.subheader("Output")

        output_filename = st.text_input(
            "Output Filename",
            value="REVIEWED_CANDIDATES.xlsx",
            help="Name for the output Excel file"
        )

        if not output_filename.endswith('.xlsx'):
            output_filename += '.xlsx'

        output_directory = str(Path.cwd())

    st.divider()

    # Display Job Analysis Results (if available)
    if 'job_analysis' in st.session_state and st.session_state.job_analysis:
        _render_job_analysis_results(st.session_state.job_analysis)

    # Process button
    if st.button("Start Processing", type="primary", use_container_width=True):
        _handle_processing(
            job_posting_file=job_posting_file,
            candidates_file=candidates_file,
            payband_standards_file=payband_standards_file,
            previous_results_file=previous_results_file,
            output_filename=output_filename,
            output_directory=output_directory,
            process_candidates=process_candidates,
            create_output_file=create_output_file,
            get_llm_client=get_llm_client,
            config=config
        )


def _render_job_analysis_results(analysis: dict):
    """Render job analysis results."""
    st.subheader("Job Analysis Results")

    # Summary
    with st.expander("Summary", expanded=True):
        st.markdown(analysis.get('summary', 'No summary available'))

    # Suggested weights
    if 'suggested_weights' in analysis:
        with st.expander("Suggested Weights", expanded=True):
            weights = analysis['suggested_weights']
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Required Skills", f"{weights.get('required_skills', 50)}%")
            with col2:
                st.metric("Preferred Skills", f"{weights.get('preferred_skills', 30)}%")
            with col3:
                st.metric("Education", f"{weights.get('education', 20)}%")

    # Detailed analysis by level
    has_multiple_levels = analysis.get('has_multiple_levels', False)
    levels = analysis.get('levels', {})

    if has_multiple_levels and len(levels) > 1:
        st.markdown("**Job Levels:**")
        for level_name, level_data in levels.items():
            with st.expander(f"{level_name}", expanded=False):
                _render_level_details(level_data)
    else:
        single_level = list(levels.values())[0] if levels else {}
        with st.expander("Detailed Requirements", expanded=False):
            _render_level_details(single_level)

    st.divider()


def _render_level_details(level_data: dict):
    """Render details for a single job level."""
    # Required Technical Skills
    st.markdown("**Required Technical Skills:**")
    req_skills = level_data.get('required_technical_skills', [])
    if req_skills:
        for skill in req_skills:
            st.markdown(f"- {skill}")
    else:
        st.markdown("- Not specified")

    st.markdown("")

    # Preferred Skills
    st.markdown("**Preferred Skills:**")
    pref_skills = level_data.get('preferred_skills', [])
    if pref_skills:
        for skill in pref_skills:
            st.markdown(f"- {skill}")
    else:
        st.markdown("- Not specified")

    st.markdown("")

    # Education
    st.markdown("**Minimum Education:**")
    st.markdown(level_data.get('minimum_education', 'Not specified'))

    st.markdown("")

    # Experience
    st.markdown("**Years of Experience Required:**")
    st.markdown(str(level_data.get('years_experience_required', 'Not specified')))


def _handle_processing(job_posting_file, candidates_file, payband_standards_file,
                       previous_results_file, output_filename, output_directory,
                       process_candidates, create_output_file, get_llm_client, config):
    """Handle the processing workflow."""
    if not job_posting_file:
        st.error("Please upload a job posting file (.txt or .rtf)")
        return

    if not candidates_file:
        st.error("Please upload a candidates Excel file (.xlsx)")
        return

    # Initialize LLM client
    try:
        client = get_llm_client()
        st.info(f"Using backend: AWS Bedrock ({config.region}) | Model: {config.model_name}")
    except Exception as e:
        st.error(f"Failed to initialize LLM client: {str(e)}")
        return

    # Load job posting
    try:
        job_posting = job_posting_file.read().decode('utf-8')
        st.success("Loaded job posting")
    except Exception as e:
        st.error(f"Could not read job posting file: {str(e)}")
        return

    # Load candidates
    try:
        df = pd.read_excel(candidates_file, header=1)
        st.success(f"Loaded {len(df)} candidates from Excel file")
    except Exception as e:
        st.error(f"Failed to load candidates file: {str(e)}")
        return

    # Load payband standards
    payband_standards_text = None
    if payband_standards_file is not None:
        try:
            payband_standards_text = payband_standards_file.read().decode('utf-8')
            st.success(f"Loaded payband standards document ({len(payband_standards_text)} characters)")
        except Exception as e:
            st.warning(f"Could not read payband standards file: {str(e)}")

    # Load previous results
    previous_results_df = None
    previous_disqualified_non_us_df = None
    previous_disqualified_no_degree_df = None
    if previous_results_file is not None:
        try:
            previous_results_df = pd.read_excel(previous_results_file, sheet_name='Ranked Candidates')
            if 'Rank' in previous_results_df.columns:
                previous_results_df = previous_results_df.drop(columns=['Rank'])
            if 'Error' not in previous_results_df.columns:
                previous_results_df['Error'] = ''
            else:
                previous_results_df['Error'] = previous_results_df['Error'].fillna('')

            total_previous = len(previous_results_df)
            try:
                previous_disqualified_non_us_df = pd.read_excel(previous_results_file, sheet_name='Disqualified - Non-US Citizens')
                total_previous += len(previous_disqualified_non_us_df)
            except:
                pass

            try:
                previous_disqualified_no_degree_df = pd.read_excel(previous_results_file, sheet_name='Disqualified - No Bachelors')
                total_previous += len(previous_disqualified_no_degree_df)
            except:
                pass

            st.success(f"Loaded previous results file ({total_previous} candidates will be skipped)")
        except Exception as e:
            st.warning(f"Could not read previous results file: {str(e)}")

    # Process candidates
    st.subheader("Processing Candidates")

    weights_to_use = st.session_state.get('custom_weights', DEFAULT_WEIGHTS)
    test_count = st.session_state.get('test_count')

    results_df, skipped_df, disqualified_non_us_df, disqualified_no_degree_df, already_processed_df = process_candidates(
        client, df, job_posting, test_count, weights_to_use,
        st.session_state.strictness, payband_standards_text,
        previous_results_df, previous_disqualified_non_us_df, previous_disqualified_no_degree_df
    )

    # Merge with previous results
    if previous_results_df is not None and len(previous_results_df) > 0:
        successfully_processed = previous_results_df[previous_results_df['Error'] == '']
        results_df = pd.concat([results_df, successfully_processed], ignore_index=True)
        st.info(f"Merged {len(successfully_processed)} previously processed candidates with {len(results_df) - len(successfully_processed)} newly processed candidates")

    if previous_disqualified_non_us_df is not None and len(previous_disqualified_non_us_df) > 0:
        disqualified_non_us_df = pd.concat([disqualified_non_us_df, previous_disqualified_non_us_df], ignore_index=True)

    if previous_disqualified_no_degree_df is not None and len(previous_disqualified_no_degree_df) > 0:
        disqualified_no_degree_df = pd.concat([disqualified_no_degree_df, previous_disqualified_no_degree_df], ignore_index=True)

    if len(results_df) == 0 and len(skipped_df) == 0 and len(disqualified_non_us_df) == 0 and len(disqualified_no_degree_df) == 0:
        st.error("No candidates were processed")
        return

    # Create output file
    output_path = Path(output_directory) / output_filename
    qualified_df, disqualified_non_us_df, disqualified_no_degree_df, errors_df, skipped_df, summary_df = create_output_file(
        results_df, skipped_df, disqualified_non_us_df, disqualified_no_degree_df, output_path
    )

    st.success(f"Processing complete! Results saved to: **{output_path}**")

    # Show summary
    _render_processing_summary(
        qualified_df, disqualified_non_us_df, disqualified_no_degree_df,
        errors_df, skipped_df, already_processed_df, results_df, output_path, output_filename
    )


def _render_processing_summary(qualified_df, disqualified_non_us_df, disqualified_no_degree_df,
                               errors_df, skipped_df, already_processed_df, results_df,
                               output_path, output_filename):
    """Render the processing summary."""
    st.divider()
    st.subheader("Summary")

    total_disqualified = len(disqualified_non_us_df) + len(disqualified_no_degree_df)
    total_in_file = len(results_df) + total_disqualified + len(skipped_df)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total in File", total_in_file)
    with col2:
        st.metric("Qualified", len(qualified_df))
    with col3:
        st.metric("Disqualified", total_disqualified)
    with col4:
        st.metric("Errors", len(errors_df))
    with col5:
        st.metric("Skipped", len(skipped_df))

    # Warnings
    if len(errors_df) > 0:
        st.warning(f"{len(errors_df)} candidate(s) had evaluation errors. Check the 'Evaluation Errors' sheet.")
    if len(skipped_df) > 0:
        st.warning(f"{len(skipped_df)} candidate(s) were skipped due to missing resume text.")
    if len(disqualified_non_us_df) > 0:
        st.warning(f"{len(disqualified_non_us_df)} candidate(s) disqualified (Non-US Citizens).")
    if len(disqualified_no_degree_df) > 0:
        st.warning(f"{len(disqualified_no_degree_df)} candidate(s) disqualified (No Bachelor's Degree).")
    if len(already_processed_df) > 0:
        st.info(f"{len(already_processed_df)} candidate(s) were already in previous results and were skipped.")

    # Verify math
    evaluated = len(qualified_df) + total_disqualified + len(errors_df)
    if evaluated + len(skipped_df) == total_in_file:
        st.success(f"All {total_in_file} candidates accounted for: {evaluated} evaluated + {len(skipped_df)} skipped")

    # Top candidates
    if len(qualified_df) > 0:
        st.subheader("Top Candidates")
        display_cols = ['Rank', 'Candidate Name', 'Overall Score', 'Years of Experience',
                       'Highest Completed Degree', 'Degree In Progress', 'Recommended Payband',
                       'Security Clearance', 'Polygraph', 'Foreign Education', 'Clearance Risk Factors']
        available_cols = [col for col in display_cols if col in qualified_df.columns]
        top_10 = qualified_df.head(10)[available_cols].copy()

        def simplify_degree(row):
            completed = row.get('Highest Completed Degree', 'None')
            in_progress = row.get('Degree In Progress', 'None')
            if in_progress and in_progress != 'None':
                return f"Pursuing {in_progress}"
            elif completed and completed != 'None':
                return completed
            else:
                return "None"

        top_10['Degree'] = top_10.apply(simplify_degree, axis=1)
        top_10 = top_10.drop(columns=['Highest Completed Degree', 'Degree In Progress'], errors='ignore')

        rename_map = {
            'Overall Score': 'Score',
            'Years of Experience': 'Yrs Exp',
            'Recommended Payband': 'Payband',
            'Security Clearance': 'Clearance',
            'Polygraph': 'Poly',
            'Foreign Education': 'Foreign Ed',
            'Clearance Risk Factors': 'Risk Factors'
        }
        top_10 = top_10.rename(columns={k: v for k, v in rename_map.items() if k in top_10.columns})
        st.write(top_10.to_html(index=False, escape=False), unsafe_allow_html=True)

    # Download button
    st.divider()
    with open(output_path, 'rb') as f:
        st.download_button(
            label="Download Results File",
            data=f,
            file_name=output_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

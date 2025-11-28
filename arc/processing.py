"""
Candidate Processing Pipeline.

This module handles the batch processing of candidates from Excel files.
"""

from datetime import datetime
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import streamlit as st

from .config import FEATURES, EXCEL_COLUMNS, DEFAULT_WEIGHTS
from .prompts import build_system_prompt
from .evaluation import evaluate_candidate

# Number of parallel workers for candidate evaluation
PARALLEL_WORKERS = 10


def extract_candidate_info(row, safe_get) -> dict:
    """Extract candidate information from a DataFrame row.

    Args:
        row: DataFrame row
        safe_get: Function to safely get values from row

    Returns:
        Dict with candidate information
    """
    # Get column names from config (or use defaults)
    us_citizen_col = EXCEL_COLUMNS.get('us_citizen_column') or 'US Citizenship'
    dual_citizen_col = EXCEL_COLUMNS.get('dual_citizen_column') or 'Dual Citizenship'
    sponsorship_col = EXCEL_COLUMNS.get('sponsorship_column') or 'Requires Sponsorship'

    return {
        'name': safe_get('Job Application', 'Unknown'),
        'email': safe_get('Email', 'Not provided'),
        'phone': safe_get('Phone', 'Not provided'),
        'location': safe_get('Address', 'Not provided'),
        'education': safe_get('Degree', 'Not specified'),
        'all_degrees': safe_get('All Degrees', ''),
        'schools_attended': safe_get('Schools Attended', ''),
        'total_years_experience': safe_get('Total Years Experience', ''),
        'current_title': safe_get('Current Title', ''),
        'current_company': safe_get('Current Company', ''),
        'all_companies': safe_get('All Companies', ''),
        'skills': safe_get('Skills', ''),
        'resume_file': safe_get('Resume', ''),
        'us_citizen_from_excel': safe_get(us_citizen_col, ''),
        'dual_citizen': safe_get(dual_citizen_col, 'No'),
        'requires_sponsorship': safe_get(sponsorship_col, 'No'),
        'work_authorized': safe_get('Are you legally authorized to work in the US? (External)', ''),
        'living_outside_us': safe_get('Are you living in a restricted state/outside of the U.S.', 'No'),
        'willing_to_relocate': safe_get('Are you willing to relocate?', 'Not specified'),
        'date_applied': safe_get('Date Applied', ''),
        'source': safe_get('Source', '')
    }


def is_us_citizen(candidate_info: dict) -> bool:
    """Check if candidate is a US citizen based on Excel data.

    Args:
        candidate_info: Dict with candidate information

    Returns:
        True if candidate is US citizen, False otherwise
    """
    us_citizen_yes_value = EXCEL_COLUMNS.get('us_citizen_yes_value', 'Yes')
    return candidate_info['us_citizen_from_excel'] == us_citizen_yes_value


def is_dual_citizen(candidate_info: dict) -> bool:
    """Check if candidate has dual citizenship based on Excel data."""
    dual_citizen_yes_value = EXCEL_COLUMNS.get('dual_citizen_yes_value', 'Yes')
    return candidate_info['dual_citizen'] == dual_citizen_yes_value


def _evaluate_single_candidate(client, candidate_data: dict, system_prompt: str) -> dict:
    """Evaluate a single candidate - designed to run in a thread.

    Args:
        client: LLM client instance
        candidate_data: Dict with 'resume_text' and 'candidate_info'
        system_prompt: Pre-built system prompt

    Returns:
        Dict with evaluation results and candidate info
    """
    resume_text = candidate_data['resume_text']
    candidate_info = candidate_data['candidate_info']

    # Evaluate candidate
    evaluation = evaluate_candidate(client, resume_text, candidate_info, system_prompt)

    # Get foreign education info from Claude's evaluation
    has_foreign_edu = evaluation.get('has_foreign_education', False)
    foreign_edu_countries = evaluation.get('foreign_education_countries', '')

    # Build clearance risk factors list
    clearance_risks = []
    if has_foreign_edu:
        clearance_risks.append(f"Foreign Education ({foreign_edu_countries})" if foreign_edu_countries else "Foreign Education")
    if candidate_info.get('requires_sponsorship') == 'Yes':
        clearance_risks.append("Requires Immigration Sponsorship")
    if is_dual_citizen(candidate_info):
        clearance_risks.append("Dual Citizenship")
    if candidate_info.get('living_outside_us') == 'Yes':
        clearance_risks.append("Living Outside US/Restricted State")

    # Build result
    return {
        'Candidate Name': candidate_info['name'],
        'Email': candidate_info['email'],
        'Phone': candidate_info.get('phone', 'Not provided'),
        'Location': candidate_info.get('location', 'Not provided'),
        'Willing to Relocate': candidate_info.get('willing_to_relocate', 'Not specified'),
        'Dual Citizenship': candidate_info.get('dual_citizen', 'No'),
        'Security Clearance': evaluation.get('security_clearance', 'Unknown'),
        'Polygraph': evaluation.get('polygraph', 'Unknown'),
        'Foreign Education': 'Yes' if has_foreign_edu else 'No',
        'Foreign Education Countries': foreign_edu_countries,
        'Foreign Education Details': evaluation.get('foreign_education_details', ''),
        'Clearance Risk Factors': '; '.join(clearance_risks) if clearance_risks else 'None identified',
        'Date Applied': candidate_info.get('date_applied', ''),
        'Date Evaluated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Overall Score': evaluation.get('overall_score', 0),
        'Required Skills Score': evaluation.get('required_skills_score', 0),
        'Preferred Skills Score': evaluation.get('preferred_skills_score', 0),
        'Education Score': evaluation.get('education_score', 0),
        'Years of Experience': evaluation.get('years_of_experience', 0),
        'Years of Experience (Adjusted)': evaluation.get('years_of_experience_adjusted', 0),
        'Recommended Payband': evaluation.get('recommended_payband', 'N/A'),
        'Highest Completed Degree': evaluation.get('highest_completed_degree', ''),
        'Degree Field': evaluation.get('highest_degree_field', ''),
        'Degree In Progress': evaluation.get('degree_in_progress', 'None'),
        'Degree In Progress Field': evaluation.get('degree_in_progress_field', ''),
        'Expected Graduation': evaluation.get('expected_graduation', ''),
        'Key Strengths': evaluation.get('key_strengths', ''),
        'Concerns/Gaps': evaluation.get('concerns_gaps', ''),
        'Detailed Reasoning': evaluation.get('detailed_reasoning', ''),
        'Error': evaluation.get('error', '')
    }


def process_candidates(client, df: pd.DataFrame, job_posting: str,
                       test_count: Optional[int] = None,
                       weights: Optional[dict] = None,
                       strictness: str = "balanced",
                       payband_standards: Optional[str] = None,
                       previous_results_df: Optional[pd.DataFrame] = None,
                       previous_disqualified_non_us_df: Optional[pd.DataFrame] = None,
                       previous_disqualified_no_degree_df: Optional[pd.DataFrame] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Process all candidates and return results.

    Args:
        client: LLM client instance (Anthropic Direct, AWS Bedrock, or GovCloud)
        df: DataFrame with candidate data
        job_posting: Text content of job posting
        test_count: If not None, process only this many candidates from the file (test mode)
        weights: Optional dict with scoring weights (required_skills, preferred_skills, education)
        strictness: "lenient", "balanced", or "strict" - controls scoring differentiation
        payband_standards: Optional text content from payband standards document
        previous_results_df: Optional DataFrame from previous processing run - qualified candidates will be skipped
        previous_disqualified_non_us_df: Optional DataFrame of previously disqualified non-US citizens
        previous_disqualified_no_degree_df: Optional DataFrame of previously disqualified candidates without degrees

    Returns:
        Tuple of (results_df, skipped_df, disqualified_non_us_df, disqualified_no_degree_df, already_processed_df)
    """
    # Default weights if not provided
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    # Build system prompt ONCE for all candidates (enables prompt caching)
    system_prompt = build_system_prompt(job_posting, weights, strictness, payband_standards)

    results = []
    skipped_candidates = []
    disqualified_non_us = []
    disqualified_no_degree = []  # DEPRECATED - no longer disqualifying based on degree
    already_processed = []

    # Build set of already-processed candidate emails from previous results
    processed_identifiers = set()
    total_previous = 0

    if previous_results_df is not None and len(previous_results_df) > 0:
        if 'Email' in previous_results_df.columns:
            successfully_processed = previous_results_df[previous_results_df['Error'] == '']
            processed_identifiers.update(successfully_processed['Email'].dropna().str.strip().str.lower())
            total_previous += len(successfully_processed)

    if previous_disqualified_non_us_df is not None and len(previous_disqualified_non_us_df) > 0:
        if 'Email' in previous_disqualified_non_us_df.columns:
            processed_identifiers.update(previous_disqualified_non_us_df['Email'].dropna().str.strip().str.lower())
            total_previous += len(previous_disqualified_non_us_df)

    if previous_disqualified_no_degree_df is not None and len(previous_disqualified_no_degree_df) > 0:
        if 'Email' in previous_disqualified_no_degree_df.columns:
            processed_identifiers.update(previous_disqualified_no_degree_df['Email'].dropna().str.strip().str.lower())
            total_previous += len(previous_disqualified_no_degree_df)

    if len(processed_identifiers) > 0:
        st.info(f"Found {len(processed_identifiers)} previously processed candidates - these will be skipped")

    # Apply test mode limit FIRST
    if test_count:
        df_to_process = df.head(test_count)
        st.info(f"Test mode: Processing first {test_count} candidates from file")
    else:
        df_to_process = df

    # Check if US citizenship filtering is enabled
    require_us_citizenship = FEATURES.get('require_us_citizenship', False)

    if require_us_citizenship:
        st.info("Scanning candidates for US citizenship and checking for duplicates...")
    else:
        st.info("Scanning candidates and checking for duplicates...")

    candidates_to_process = []

    for idx, row in df_to_process.iterrows():
        def safe_get(col_name, default=''):
            val = row.get(col_name, default)
            if pd.isna(val):
                return default
            return val

        candidate_info = extract_candidate_info(row, safe_get)

        # Check if already processed
        candidate_email_lower = str(candidate_info['email']).strip().lower()
        if candidate_email_lower in processed_identifiers:
            already_processed.append({
                'Candidate Name': candidate_info['name'],
                'Email': candidate_info['email'],
                'Note': 'Already processed in previous run'
            })
            continue

        # US citizenship check (only if feature enabled)
        if require_us_citizenship:
            if is_us_citizen(candidate_info):
                candidates_to_process.append((idx, row, candidate_info))
            else:
                disqualified_non_us.append({
                    'Candidate Name': candidate_info['name'],
                    'Email': candidate_info['email'],
                    'Education Level': candidate_info['education'],
                    'Resume File': candidate_info['resume_file'],
                    'Disqualification Reason': 'Not a U.S. Citizen (Required for classified work)'
                })
        else:
            # Process all candidates when citizenship not required
            candidates_to_process.append((idx, row, candidate_info))

    # Show summary of filtering
    new_candidates_count = len(df_to_process) - len(already_processed)
    candidates_count = len(candidates_to_process)
    non_us_count = len(disqualified_non_us)

    if require_us_citizenship:
        st.success(f"Found {candidates_count} US citizens out of {new_candidates_count} candidates")
        if non_us_count > 0:
            st.warning(f"Auto-disqualified {non_us_count} non-US citizens (will not be sent to Claude)")
    else:
        st.success(f"Found {candidates_count} candidates to process")

    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Filter out candidates without resume text first
    valid_candidates = []
    for idx, row, candidate_info in candidates_to_process:
        resume_text = row.get('Resume Text', '')

        if not resume_text or pd.isna(resume_text):
            skipped_candidates.append({
                'Candidate Name': candidate_info['name'],
                'Email': candidate_info['email'],
                'Education Level': candidate_info['education'],
                'Resume File': candidate_info['resume_file'],
                'Reason': 'No resume text available'
            })
        else:
            valid_candidates.append({
                'resume_text': resume_text,
                'candidate_info': candidate_info
            })

    if len(skipped_candidates) > 0:
        st.warning(f"Skipping {len(skipped_candidates)} candidate(s) - No resume text found")

    total_valid = len(valid_candidates)
    if total_valid == 0:
        st.warning("No valid candidates to process")
        return (
            pd.DataFrame(results),
            pd.DataFrame(skipped_candidates),
            pd.DataFrame(disqualified_non_us),
            pd.DataFrame(disqualified_no_degree),
            pd.DataFrame(already_processed)
        )

    # Process candidates in parallel
    st.info(f"Processing {total_valid} candidates...")
    completed_count = 0

    with st.spinner("Processing resumes with Claude AI..."):
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            # Submit all tasks
            future_to_candidate = {
                executor.submit(_evaluate_single_candidate, client, candidate_data, system_prompt): candidate_data
                for candidate_data in valid_candidates
            }

            # Process results as they complete
            for future in as_completed(future_to_candidate):
                completed_count += 1
                candidate_data = future_to_candidate[future]
                candidate_name = candidate_data['candidate_info']['name']

                status_text.text(f"Completed {completed_count} of {total_valid} ({candidate_name})")
                progress_bar.progress(completed_count / total_valid)

                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    # Handle any unexpected errors
                    results.append({
                        'Candidate Name': candidate_name,
                        'Email': candidate_data['candidate_info']['email'],
                        'Error': f"Processing error: {str(e)}"
                    })

    return (
        pd.DataFrame(results),
        pd.DataFrame(skipped_candidates),
        pd.DataFrame(disqualified_non_us),
        pd.DataFrame(disqualified_no_degree),
        pd.DataFrame(already_processed)
    )

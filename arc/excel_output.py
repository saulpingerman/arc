"""
Excel Output Generation Module.

This module handles the creation of Excel output files with candidate results.
"""

import pandas as pd
from pathlib import Path
from typing import Tuple

from .config import FEATURES, EXCEL_COLUMNS


def create_output_file(results_df: pd.DataFrame,
                       skipped_df: pd.DataFrame,
                       disqualified_non_us_df: pd.DataFrame,
                       disqualified_no_degree_df: pd.DataFrame,
                       output_path: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create Excel file with multiple sheets.

    Args:
        results_df: DataFrame with evaluation results
        skipped_df: DataFrame with skipped candidates
        disqualified_non_us_df: DataFrame with non-US citizens
        disqualified_no_degree_df: DataFrame with candidates without degrees
        output_path: Path for output file

    Returns:
        Tuple of (qualified_df, disqualified_non_us_df, disqualified_no_degree_df, errors_df, skipped_df, summary_df)
    """
    # Separate results into qualified and errors
    errors_df = results_df[results_df['Error'] != ''].copy()
    qualified_df = results_df[results_df['Error'] == ''].copy()

    # Format Date Applied
    if 'Date Applied' in qualified_df.columns:
        qualified_df['Date Applied'] = pd.to_datetime(qualified_df['Date Applied'], errors='coerce').dt.strftime('%Y-%m-%d')
    if 'Date Applied' in errors_df.columns:
        errors_df['Date Applied'] = pd.to_datetime(errors_df['Date Applied'], errors='coerce').dt.strftime('%Y-%m-%d')

    # Remove unnecessary columns
    columns_to_remove = ['Willing to Relocate', 'Date Evaluated']
    for col in columns_to_remove:
        if col in qualified_df.columns:
            qualified_df = qualified_df.drop(columns=[col])
        if col in errors_df.columns:
            errors_df = errors_df.drop(columns=[col])

    # Sort and rank qualified candidates
    if len(qualified_df) > 0:
        qualified_df = qualified_df.sort_values('Overall Score', ascending=False)
        qualified_df.insert(0, 'Rank', range(1, len(qualified_df) + 1))

        # Reorder columns for optimal viewing
        column_order = [
            'Rank',
            'Candidate Name',
            'Email',
            'Overall Score',
            'Years of Experience',
            'Highest Completed Degree',
            'Recommended Payband',
            'Security Clearance',
            'Polygraph',
            'Clearance Risk Factors',
            'Degree Field',
            'Degree In Progress',
            'Degree In Progress Field',
            'Expected Graduation',
            'Key Strengths',
            'Concerns/Gaps',
            'Date Applied',
            'Required Skills Score',
            'Preferred Skills Score',
            'Education Score',
            'Years of Experience (Adjusted)',
            'Dual Citizenship',
            'Foreign Education',
            'Foreign Education Countries',
            'Foreign Education Details',
            'Phone',
            'Location',
            'Detailed Reasoning',
            'Error'
        ]
        column_order = [col for col in column_order if col in qualified_df.columns]
        remaining_cols = [col for col in qualified_df.columns if col not in column_order]
        qualified_df = qualified_df[column_order + remaining_cols]

    # Simplify errors view
    errors_simple = errors_df[[
        'Candidate Name', 'Email', 'Highest Completed Degree', 'Degree Field', 'Error'
    ]].copy() if len(errors_df) > 0 else pd.DataFrame()

    # Create summary stats
    summary_df = _create_summary(qualified_df, disqualified_non_us_df, disqualified_no_degree_df, errors_df, skipped_df, results_df)

    # Write to Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        if len(qualified_df) > 0:
            qualified_df.to_excel(writer, sheet_name='Ranked Candidates', index=False)
        if len(disqualified_non_us_df) > 0:
            disqualified_non_us_df.to_excel(writer, sheet_name='Disqualified - Non-US Citizens', index=False)
        if len(disqualified_no_degree_df) > 0:
            disqualified_no_degree_df.to_excel(writer, sheet_name='Disqualified - No Bachelors', index=False)
        if len(errors_df) > 0:
            errors_simple.to_excel(writer, sheet_name='Evaluation Errors', index=False)
        if len(skipped_df) > 0:
            skipped_df.to_excel(writer, sheet_name='Skipped - No Resume', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    return qualified_df, disqualified_non_us_df, disqualified_no_degree_df, errors_df, skipped_df, summary_df


def _create_summary(qualified_df: pd.DataFrame,
                    disqualified_non_us_df: pd.DataFrame,
                    disqualified_no_degree_df: pd.DataFrame,
                    errors_df: pd.DataFrame,
                    skipped_df: pd.DataFrame,
                    results_df: pd.DataFrame) -> pd.DataFrame:
    """Create summary statistics DataFrame."""

    total_disqualified = len(disqualified_non_us_df) + len(disqualified_no_degree_df)
    total_candidates = len(results_df) + total_disqualified + len(skipped_df)

    summary_metrics = [
        'Total Candidates in File',
        'Successfully Evaluated',
        'Qualified',
        'Disqualified (Non-US Citizens)',
        'Disqualified (No Bachelor\'s Degree)',
        'Total Disqualified',
        'Evaluation Errors',
        'Skipped (No Resume Text)',
        'Average Score (Qualified)',
        'Highest Score',
    ]

    summary_values = [
        total_candidates,
        len(results_df),
        len(qualified_df),
        len(disqualified_non_us_df),
        len(disqualified_no_degree_df),
        total_disqualified,
        len(errors_df),
        len(skipped_df),
        f"{qualified_df['Overall Score'].mean():.1f}" if len(qualified_df) > 0 else "N/A",
        f"{qualified_df['Overall Score'].max():.0f}" if len(qualified_df) > 0 else "N/A",
    ]

    # Add clearance stats if tracking is enabled
    if FEATURES.get('track_clearance', True) and len(qualified_df) > 0:
        summary_metrics.extend([
            '--- Clearance Status ---',
            'Clearance - Top Secret/SCI',
            'Clearance - Top Secret',
            'Clearance - Secret',
            'Clearance - Confidential',
            'Clearance - Unclassified',
            'Clearance - Unknown',
            'Polygraph - Full Scope (FS)',
            'Polygraph - Counter Intelligence (CI)',
            'Polygraph - Unknown',
            '--- Clearance Risk Factors ---',
            'Has Foreign Education',
            'Has Dual Citizenship',
            'Requires Immigration Sponsorship',
            'Living Outside US/Restricted State',
            'No Risk Factors Identified'
        ])

        # Calculate risk factor counts
        dual_citizen_yes = EXCEL_COLUMNS.get('dual_citizen_yes_value', 'Yes')
        foreign_edu_count = len(qualified_df[qualified_df['Foreign Education'] == 'Yes']) if 'Foreign Education' in qualified_df.columns else 0
        dual_citizen_count = len(qualified_df[qualified_df['Dual Citizenship'] == dual_citizen_yes]) if 'Dual Citizenship' in qualified_df.columns else 0
        sponsorship_count = len(qualified_df[qualified_df['Clearance Risk Factors'].str.contains('Immigration Sponsorship', na=False)]) if 'Clearance Risk Factors' in qualified_df.columns else 0
        outside_us_count = len(qualified_df[qualified_df['Clearance Risk Factors'].str.contains('Living Outside', na=False)]) if 'Clearance Risk Factors' in qualified_df.columns else 0
        no_risks_count = len(qualified_df[qualified_df['Clearance Risk Factors'] == 'None identified']) if 'Clearance Risk Factors' in qualified_df.columns else 0

        summary_values.extend([
            '',  # Section header
            len(qualified_df[qualified_df['Security Clearance'] == 'Top Secret/SCI']),
            len(qualified_df[qualified_df['Security Clearance'] == 'Top Secret']),
            len(qualified_df[qualified_df['Security Clearance'] == 'Secret']),
            len(qualified_df[qualified_df['Security Clearance'] == 'Confidential']),
            len(qualified_df[qualified_df['Security Clearance'] == 'Unclassified']),
            len(qualified_df[qualified_df['Security Clearance'] == 'Unknown']),
            len(qualified_df[qualified_df['Polygraph'] == 'FS']),
            len(qualified_df[qualified_df['Polygraph'] == 'CI']),
            len(qualified_df[qualified_df['Polygraph'] == 'Unknown']),
            '',  # Section header
            foreign_edu_count,
            dual_citizen_count,
            sponsorship_count,
            outside_us_count,
            no_risks_count
        ])

    # Add payband counts
    if len(qualified_df) > 0:
        unique_paybands = qualified_df['Recommended Payband'].value_counts().sort_index()
        for payband, count in unique_paybands.items():
            summary_metrics.append(f'Recommended for {payband}')
            summary_values.append(count)

    return pd.DataFrame({
        'Metric': summary_metrics,
        'Value': summary_values
    })

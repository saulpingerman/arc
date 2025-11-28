"""
Local Configuration Example - Organization-Specific Settings
============================================================
Copy this file to local_config.py and customize for your organization.
local_config.py is gitignored and will not be committed.

This file contains organization-specific settings like:
- Author/contact information
- Excel column mappings for your HR system
- Feature flags for your deployment
"""

# =============================================================================
# ORGANIZATION BRANDING
# =============================================================================
# Your name and contact email displayed in the app sidebar
AUTHOR_NAME = "Your Name"
AUTHOR_EMAIL = "your.email@example.com"

# =============================================================================
# EXCEL COLUMN MAPPINGS
# =============================================================================
# These map to specific column names in your organization's candidate Excel exports.
# Customize these to match your HR system's export format.

EXCEL_COLUMNS = {
    # US Citizenship column name and the value that indicates "Yes"
    # Set to None if your organization doesn't track this
    'us_citizen_column': None,  # e.g., 'US Citizenship Status'
    'us_citizen_yes_value': 'Yes',  # e.g., 'Yes', 'US Citizen', etc.

    # Dual citizenship column name and the value that indicates "Yes"
    # Set to None if your organization doesn't track this
    'dual_citizen_column': None,  # e.g., 'Dual Citizenship'
    'dual_citizen_yes_value': 'Yes',

    # Immigration sponsorship question column
    # Set to None if your organization doesn't track this
    'sponsorship_column': None,  # e.g., 'Requires Sponsorship'
}

# =============================================================================
# FEATURE FLAGS
# =============================================================================
# Enable/disable organization-specific features

FEATURES = {
    # Show author info in sidebar
    'show_author_info': False,

    # Require US citizenship (for classified/government work)
    # If False, citizenship filtering is disabled
    'require_us_citizenship': False,

    # Track security clearance information from resumes
    'track_clearance': False,
}

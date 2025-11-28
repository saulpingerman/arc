"""
Configuration settings for ARC application.

This module contains all configuration constants including AWS backend settings.
Organization-specific settings are loaded from local_config.py (if present).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
import sys
from pathlib import Path


class Environment(Enum):
    """Deployment environment options."""
    COMMERCIAL = "commercial"
    GOVCLOUD = "govcloud"


@dataclass
class AWSConfig:
    """AWS backend configuration."""
    backend_type: str
    model_id: str
    model_name: str
    region: str


# =============================================================================
# AWS BACKEND CONFIGURATION
# =============================================================================
# To switch between Commercial AWS and GovCloud, change ACTIVE_ENVIRONMENT below:

ACTIVE_ENVIRONMENT = Environment.COMMERCIAL  # Change to Environment.GOVCLOUD for production

# Configuration for each environment
AWS_CONFIGS = {
    Environment.COMMERCIAL: AWSConfig(
        backend_type="AWS_BEDROCK",
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        model_name="Claude Sonnet 4.5",
        region="us-east-1"
    ),
    Environment.GOVCLOUD: AWSConfig(
        backend_type="AWS_GOVCLOUD",
        model_id="us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0",
        model_name="Claude Sonnet 4.5",
        region="us-gov-west-1"
    )
}


def get_active_config() -> AWSConfig:
    """Get the currently active AWS configuration."""
    return AWS_CONFIGS[ACTIVE_ENVIRONMENT]


# =============================================================================
# DEFAULT SETTINGS (can be overridden by local_config.py)
# =============================================================================

# Default scoring weights
DEFAULT_WEIGHTS = {
    'required_skills': 50,
    'preferred_skills': 30,
    'education': 20
}

# Scoring strictness options
STRICTNESS_OPTIONS = ["lenient", "balanced", "strict"]
DEFAULT_STRICTNESS = "strict"

# Application metadata
APP_NAME = "ARC"
APP_FULL_NAME = "AI Resume Critique"
APP_VERSION = "1.0.0"

# Default organization settings (overridden by local_config.py if present)
AUTHOR_NAME = None
AUTHOR_EMAIL = None

# Default Excel column mappings (generic)
EXCEL_COLUMNS = {
    'us_citizen_column': None,
    'us_citizen_yes_value': 'Yes',
    'dual_citizen_column': None,
    'dual_citizen_yes_value': 'Yes',
    'sponsorship_column': None,
}

# Default feature flags
FEATURES = {
    'show_author_info': False,
    'require_us_citizenship': False,
    'track_clearance': True,
}


# =============================================================================
# LOAD LOCAL CONFIG (if present)
# =============================================================================
def _load_local_config():
    """Load organization-specific settings from local_config.py if it exists."""
    global AUTHOR_NAME, AUTHOR_EMAIL, EXCEL_COLUMNS, FEATURES

    # Add parent directory to path to find local_config
    parent_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_dir))

    try:
        import local_config

        if hasattr(local_config, 'AUTHOR_NAME'):
            AUTHOR_NAME = local_config.AUTHOR_NAME
        if hasattr(local_config, 'AUTHOR_EMAIL'):
            AUTHOR_EMAIL = local_config.AUTHOR_EMAIL
        if hasattr(local_config, 'EXCEL_COLUMNS'):
            EXCEL_COLUMNS.update(local_config.EXCEL_COLUMNS)
        if hasattr(local_config, 'FEATURES'):
            FEATURES.update(local_config.FEATURES)

    except ImportError:
        # local_config.py doesn't exist, use defaults
        pass
    finally:
        # Remove from path
        if str(parent_dir) in sys.path:
            sys.path.remove(str(parent_dir))


# Load local config on module import
_load_local_config()

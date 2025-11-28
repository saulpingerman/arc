"""
Candidate Evaluation Module.

This module handles the evaluation of individual candidates using the LLM.
"""

import json
import time
import random
from typing import Optional

from .prompts import build_system_prompt, build_job_analysis_prompt, build_candidate_evaluation_message

# Retry configuration for throttling errors
MAX_RETRIES = 3
BASE_DELAY = 2  # seconds
MAX_DELAY = 30  # seconds


def analyze_job_posting(client, job_posting: str) -> dict:
    """Analyze job posting to extract required skills and suggest weights.

    Args:
        client: LLM client instance
        job_posting: Text content of the job posting

    Returns:
        Dict with job analysis results or error information
    """
    prompt = build_job_analysis_prompt(job_posting)

    try:
        content = client.create_message(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        json_start = content.find('{')
        json_end = content.rfind('}') + 1

        if json_start != -1 and json_end > json_start:
            json_str = content[json_start:json_end]
            return json.loads(json_str)
        else:
            return {"error": "Could not parse job analysis"}

    except Exception as e:
        return {"error": f"Job Analysis Error: {str(e)}"}


def _is_throttling_error(error: Exception) -> bool:
    """Check if an error is a throttling/rate limit error."""
    error_str = str(error).lower()
    return any(term in error_str for term in [
        'throttl', 'rate limit', 'too many requests', 'serviceunav', '429', '503'
    ])


def evaluate_candidate(client, resume_text: str, candidate_info: dict,
                       system_prompt: str) -> dict:
    """Evaluate a single candidate using LLM API with retry logic.

    Args:
        client: LLM client instance (Anthropic Direct, AWS Bedrock, or GovCloud)
        resume_text: The candidate's resume text
        candidate_info: Dict with candidate metadata from application
        system_prompt: Pre-built system prompt (should be reused across candidates for caching)

    Returns:
        Dict with evaluation results or error information
    """
    user_message = build_candidate_evaluation_message(resume_text, candidate_info)

    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result_text = client.create_message(
                messages=[{"role": "user", "content": user_message}],
                max_tokens=2000,
                system=system_prompt
            ).strip()

            # Parse JSON response
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            result = json.loads(result_text)
            return result

        except json.JSONDecodeError as e:
            return {
                "error": f"JSON Parse Error: {str(e)}",
                "us_citizen": False,
                "overall_score": 0
            }
        except Exception as e:
            last_error = e
            if _is_throttling_error(e) and attempt < MAX_RETRIES:
                # Exponential backoff with jitter
                delay = min(BASE_DELAY * (2 ** attempt) + random.uniform(0, 1), MAX_DELAY)
                time.sleep(delay)
                continue
            else:
                # Non-throttling error or max retries exceeded
                break

    return {
        "error": f"API Error: {str(last_error)}",
        "us_citizen": False,
        "overall_score": 0
    }

"""
LLM Client Abstraction Layer for ARC

This module provides a unified interface for interacting with different LLM backends:
- Anthropic Direct API
- AWS Bedrock (Commercial)
- AWS Bedrock GovCloud

Configuration is handled via environment variables or a config file.
"""

import os
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class LLMBackend(Enum):
    """Supported LLM backends"""
    ANTHROPIC_DIRECT = "anthropic_direct"
    AWS_BEDROCK = "aws_bedrock"
    AWS_GOVCLOUD = "aws_govcloud"


@dataclass
class LLMConfig:
    """Configuration for LLM client"""
    backend: LLMBackend
    model_id: str

    # Anthropic Direct settings
    anthropic_api_key: Optional[str] = None

    # AWS settings (shared by Bedrock and GovCloud)
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None  # For temporary credentials
    aws_profile: Optional[str] = None  # For using named profiles

    @classmethod
    def from_env(cls) -> 'LLMConfig':
        """Load configuration from environment variables"""
        backend_str = os.getenv('ARC_LLM_BACKEND', 'anthropic_direct').lower()

        try:
            backend = LLMBackend(backend_str)
        except ValueError:
            raise ValueError(f"Invalid backend: {backend_str}. Must be one of: {[b.value for b in LLMBackend]}")

        # Default model IDs per backend
        default_models = {
            LLMBackend.ANTHROPIC_DIRECT: "claude-sonnet-4-5-20250929",
            LLMBackend.AWS_BEDROCK: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            LLMBackend.AWS_GOVCLOUD: "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        }

        # Default regions per backend
        default_regions = {
            LLMBackend.ANTHROPIC_DIRECT: None,
            LLMBackend.AWS_BEDROCK: "us-east-1",
            LLMBackend.AWS_GOVCLOUD: "us-gov-west-1",
        }

        return cls(
            backend=backend,
            model_id=os.getenv('ARC_MODEL_ID', default_models[backend]),
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY') or os.getenv('ARC_ANTHROPIC_API_KEY'),
            aws_region=os.getenv('AWS_REGION') or os.getenv('ARC_AWS_REGION') or default_regions[backend],
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
            aws_profile=os.getenv('AWS_PROFILE') or os.getenv('ARC_AWS_PROFILE'),
        )

    @classmethod
    def from_file(cls, config_path: Optional[Path] = None) -> 'LLMConfig':
        """Load configuration from a JSON config file"""
        if config_path is None:
            config_path = Path.home() / '.arc_llm_config.json'

        if not config_path.exists():
            # Fall back to environment variables
            return cls.from_env()

        with open(config_path, 'r') as f:
            config_data = json.load(f)

        backend_str = config_data.get('backend', 'anthropic_direct').lower()
        try:
            backend = LLMBackend(backend_str)
        except ValueError:
            raise ValueError(f"Invalid backend in config: {backend_str}")

        return cls(
            backend=backend,
            model_id=config_data.get('model_id', "claude-sonnet-4-5-20250929"),
            anthropic_api_key=config_data.get('anthropic_api_key'),
            aws_region=config_data.get('aws_region'),
            aws_access_key_id=config_data.get('aws_access_key_id'),
            aws_secret_access_key=config_data.get('aws_secret_access_key'),
            aws_session_token=config_data.get('aws_session_token'),
            aws_profile=config_data.get('aws_profile'),
        )

    def save_to_file(self, config_path: Optional[Path] = None):
        """Save configuration to a JSON config file (excluding sensitive keys)"""
        if config_path is None:
            config_path = Path.home() / '.arc_llm_config.json'

        # Only save non-sensitive configuration
        config_data = {
            'backend': self.backend.value,
            'model_id': self.model_id,
            'aws_region': self.aws_region,
            'aws_profile': self.aws_profile,
            # Note: API keys and secrets should be in environment variables, not config file
        }

        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    def create_message(self, messages: list, max_tokens: int = 2000, system: Optional[str] = None) -> str:
        """
        Send a message to the LLM and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            max_tokens: Maximum tokens in response
            system: Optional system prompt (will be cached for efficiency)

        Returns:
            The text content of the LLM's response
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Return a human-readable name for this backend"""
        pass

    @abstractmethod
    def get_model_id(self) -> str:
        """Return the model ID being used"""
        pass


class AnthropicDirectClient(BaseLLMClient):
    """Client for Anthropic's direct API"""

    def __init__(self, config: LLMConfig):
        if not config.anthropic_api_key:
            raise ValueError("Anthropic API key is required for direct API access")

        # Import here to avoid requiring the package if not used
        from anthropic import Anthropic
        import httpx

        self.config = config
        # Disable SSL verification for corporate environments
        self.client = Anthropic(
            api_key=config.anthropic_api_key,
            http_client=httpx.Client(verify=False)
        )
        self._model_id = config.model_id

    def create_message(self, messages: list, max_tokens: int = 2000, system: Optional[str] = None) -> str:
        kwargs = {
            "model": self._model_id,
            "max_tokens": max_tokens,
            "messages": messages
        }

        # Add system prompt with caching if provided
        if system:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def get_backend_name(self) -> str:
        return "Anthropic Direct API"

    def get_model_id(self) -> str:
        return self._model_id


class AWSBedrockClient(BaseLLMClient):
    """Client for AWS Bedrock (Commercial regions)"""

    def __init__(self, config: LLMConfig):
        import boto3

        self.config = config
        self._model_id = config.model_id

        # Build session kwargs
        session_kwargs = {}
        if config.aws_profile:
            session_kwargs['profile_name'] = config.aws_profile
        if config.aws_region:
            session_kwargs['region_name'] = config.aws_region

        # Create session
        session = boto3.Session(**session_kwargs)

        # If explicit credentials provided, use them
        client_kwargs = {}
        if config.aws_access_key_id and config.aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = config.aws_access_key_id
            client_kwargs['aws_secret_access_key'] = config.aws_secret_access_key
            if config.aws_session_token:
                client_kwargs['aws_session_token'] = config.aws_session_token

        self.client = session.client('bedrock-runtime', **client_kwargs)

    def create_message(self, messages: list, max_tokens: int = 2000, system: Optional[str] = None) -> str:
        # Format request for Bedrock's Anthropic Claude models
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages
        }

        # Add system prompt with caching if provided
        if system:
            request_body["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]

        response = self.client.invoke_model(
            modelId=self._model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json"
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def get_backend_name(self) -> str:
        return f"AWS Bedrock ({self.config.aws_region})"

    def get_model_id(self) -> str:
        return self._model_id


class AWSGovCloudClient(BaseLLMClient):
    """Client for AWS Bedrock in GovCloud regions"""

    def __init__(self, config: LLMConfig):
        import boto3

        self.config = config
        self._model_id = config.model_id

        # Ensure we're using a GovCloud region
        region = config.aws_region or 'us-gov-west-1'
        if not region.startswith('us-gov-'):
            # Auto-correct to GovCloud region
            region = 'us-gov-west-1'

        # Build session kwargs
        session_kwargs = {'region_name': region}
        if config.aws_profile:
            session_kwargs['profile_name'] = config.aws_profile

        # Create session
        session = boto3.Session(**session_kwargs)

        # If explicit credentials provided, use them
        client_kwargs = {}
        if config.aws_access_key_id and config.aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = config.aws_access_key_id
            client_kwargs['aws_secret_access_key'] = config.aws_secret_access_key
            if config.aws_session_token:
                client_kwargs['aws_session_token'] = config.aws_session_token

        self.client = session.client('bedrock-runtime', **client_kwargs)
        self._region = region

    def create_message(self, messages: list, max_tokens: int = 2000, system: Optional[str] = None) -> str:
        # Format request for Bedrock's Anthropic Claude models
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": messages
        }

        # Add system prompt with caching if provided
        if system:
            request_body["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]

        response = self.client.invoke_model(
            modelId=self._model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json"
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def get_backend_name(self) -> str:
        return f"AWS GovCloud Bedrock ({self._region})"

    def get_model_id(self) -> str:
        return self._model_id


def create_llm_client(config: Optional[LLMConfig] = None) -> BaseLLMClient:
    """
    Factory function to create the appropriate LLM client based on configuration.

    Args:
        config: Optional LLMConfig. If not provided, loads from environment/config file.

    Returns:
        An LLM client instance
    """
    if config is None:
        # Try config file first, then fall back to environment
        config = LLMConfig.from_file()

    if config.backend == LLMBackend.ANTHROPIC_DIRECT:
        return AnthropicDirectClient(config)
    elif config.backend == LLMBackend.AWS_BEDROCK:
        return AWSBedrockClient(config)
    elif config.backend == LLMBackend.AWS_GOVCLOUD:
        return AWSGovCloudClient(config)
    else:
        raise ValueError(f"Unknown backend: {config.backend}")


def get_available_backends() -> Dict[str, str]:
    """
    Return a dict of available backends and their descriptions.
    Checks if required dependencies are installed.
    """
    backends = {}

    # Anthropic Direct is always available if anthropic package is installed
    try:
        import anthropic
        backends[LLMBackend.ANTHROPIC_DIRECT.value] = "Anthropic Direct API (requires API key)"
    except ImportError:
        pass

    # AWS Bedrock requires boto3
    try:
        import boto3
        backends[LLMBackend.AWS_BEDROCK.value] = "AWS Bedrock (Commercial)"
        backends[LLMBackend.AWS_GOVCLOUD.value] = "AWS Bedrock GovCloud (FedRAMP High)"
    except ImportError:
        pass

    return backends


# Convenience function for quick API key based initialization (backwards compatible)
def create_anthropic_client(api_key: str) -> BaseLLMClient:
    """
    Create an Anthropic Direct client with just an API key.
    This maintains backwards compatibility with the original arc.py code.
    """
    config = LLMConfig(
        backend=LLMBackend.ANTHROPIC_DIRECT,
        model_id="claude-sonnet-4-5-20250929",
        anthropic_api_key=api_key
    )
    return AnthropicDirectClient(config)

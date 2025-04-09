"""
Factory module for creating LLM provider instances.
"""

import os
from audible.utils.common import log
from audible.llm.openai_llm import OpenAILLM
from audible.llm.anthropic_llm import AnthropicLLM
from audible.llm.google_llm import GoogleLLM

class LLMFactory:
    """Factory class for creating LLM provider instances."""

    @staticmethod
    def create(provider="openai", model=None, temperature=0.0):
        """
        Create an instance of the appropriate LLM provider.

        Args:
            provider: String specifying the LLM provider ('openai', 'anthropic', or 'google')
            model: Model name to use (provider-specific)
            temperature: Temperature value for generation (0.0-1.0)

        Returns:
            An instance of the specified LLM provider
        """
        provider = provider.lower()

        # Set default models based on provider
        if model is None:
            if provider == "openai":
                model = "o3-mini"  # Default OpenAI model
            elif provider == "anthropic":
                model = "claude-3-sonnet-20240229"  # Default Anthropic model
            elif provider == "google":
                model = "gemini-1.5-pro"  # Default Google model

        # Validate that we have the appropriate API key
        if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            log("OPENAI_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")

        if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
            log("ANTHROPIC_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic provider")

        if provider == "google" and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            credentials_path = "credentials.json"
            if os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
                log(f"Setting GOOGLE_APPLICATION_CREDENTIALS to {credentials_path}")
            else:
                log("GOOGLE_APPLICATION_CREDENTIALS not found in environment variables and credentials.json not found", level="WARNING")

        # Create the appropriate provider
        if provider == "openai":
            log(f"Creating OpenAI LLM with model {model}")
            return OpenAILLM(model=model, temperature=temperature)
        elif provider == "anthropic":
            log(f"Creating Anthropic LLM with model {model}")
            return AnthropicLLM(model=model, temperature=temperature)
        elif provider == "google":
            log(f"Creating Google LLM with model {model}")
            return GoogleLLM(model=model, temperature=temperature)
        else:
            log(f"Unknown LLM provider: {provider}", level="ERROR")
            raise ValueError(f"Unknown LLM provider: {provider}. Supported providers: openai, anthropic, google")
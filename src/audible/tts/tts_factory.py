"""
Factory module for creating TTS provider instances.
"""

import os
from audible.utils.common import log

class TTSFactory:
    """Factory class for creating TTS provider instances."""

    @staticmethod
    def create(provider="openai", model=None, use_cloned_voices=False):
        """
        Create an instance of the appropriate TTS provider.

        Args:
            provider: String specifying the TTS provider ('openai', 'cartesia', 'google', or 'csm')
            model: Model name to use (provider-specific)
            use_cloned_voices: Whether to use cloned voices when available (Cartesia only)

        Returns:
            An instance of the specified TTS provider
        """
        provider = provider.lower()

        # Set default models based on provider
        if model is None:
            if provider == "openai":
                from audible.tts.openai_tts import OpenAITTS
                model = "gpt-4o-mini-tts"  # Default OpenAI TTS model
            elif provider == "cartesia":
                from audible.tts.cartesia_tts import CartesiaTTS
                model = "sonic-2"  # Default Cartesia TTS model
            elif provider == "google":
                from audible.tts.google_tts import GoogleTTS
                model = "en-US-Neural2-D"  # Default Google TTS model
            elif provider == "csm":
                from audible.tts.csm_tts import CSMTTS
                model = "csm-1b"  # Default CSM TTS model

        # Validate that we have the appropriate API key
        if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            log("OPENAI_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")

        if provider == "cartesia" and not os.getenv("CARTESIA_API_KEY"):
            log("CARTESIA_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("CARTESIA_API_KEY environment variable is required for Cartesia provider")

        if provider == "google" and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            credentials_path = "credentials.json"
            if os.path.exists(credentials_path):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
                log(f"Setting GOOGLE_APPLICATION_CREDENTIALS to {credentials_path}")
            else:
                log("GOOGLE_APPLICATION_CREDENTIALS not found in environment variables and credentials.json not found", level="WARNING")

        # Create the appropriate provider
        if provider == "openai":
            log(f"Creating OpenAI TTS with model {model}")
            return OpenAITTS(model=model)
        elif provider == "cartesia":
            log(f"Creating Cartesia TTS with model {model} (use_cloned_voices={use_cloned_voices})")
            return CartesiaTTS(model=model, use_cloned_voices=use_cloned_voices)
        elif provider == "google":
            log(f"Creating Google TTS with model {model}")
            return GoogleTTS(model=model)
        elif provider == "csm":
            log(f"Creating CSM TTS with model {model}")
            return CSMTTS(model=model)
        else:
            log(f"Unknown TTS provider: {provider}", level="ERROR")
            raise ValueError(f"Unknown TTS provider: {provider}. Supported providers: openai, cartesia, google, csm")
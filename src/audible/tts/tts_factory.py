"""
Factory module for creating TTS provider instances.
"""

import os
from audible.utils.common import log

class TTSFactory:
    """Factory class for creating TTS provider instances."""

    @staticmethod
    def create(provider="openai", model=None, use_cloned_voices=False, multi_speaker=False):
        """
        Create an instance of the appropriate TTS provider.

        Args:
            provider: String specifying the TTS provider ('openai', 'cartesia', 'google', or 'csm')
            model: Model name to use (provider-specific)
            use_cloned_voices: Whether to use cloned voices when available (Cartesia only)
            multi_speaker: Whether to use multi-speaker audio generation (Google only)

        Returns:
            An instance of the specified TTS provider
        """
        provider = provider.lower()

        # Set default models based on provider
        if model is None:
            if provider == "openai":
                model = "gpt-4o-mini-tts"  # Default OpenAI TTS model
            elif provider == "cartesia":
                model = "sonic-2"  # Default Cartesia TTS model
            elif provider == "google":
                model = "gemini-2.5-flash-preview-tts"  # Default Google TTS model
            elif provider == "csm":
                model = "csm-1b"  # Default CSM TTS model

        # Validate that we have the appropriate API key
        if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            log("OPENAI_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI provider")

        if provider == "cartesia" and not os.getenv("CARTESIA_API_KEY"):
            log("CARTESIA_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("CARTESIA_API_KEY environment variable is required for Cartesia provider")

        if provider == "google":
            # Check for Gemini API key
            if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
                log("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables", level="ERROR")
                raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required for Google/Gemini provider")
            else:
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                log(f"Found API key for Google/Gemini provider: {api_key[:10]}...")

        # Create the appropriate provider
        if provider == "openai":
            from audible.tts.openai_tts import OpenAITTS
            log(f"Creating OpenAI TTS with model {model}")
            return OpenAITTS(model=model)
        elif provider == "cartesia":
            from audible.tts.cartesia_tts import CartesiaTTS
            log(f"Creating Cartesia TTS with model {model} (use_cloned_voices={use_cloned_voices})")
            return CartesiaTTS(model=model, use_cloned_voices=use_cloned_voices)
        elif provider == "google":
            from audible.tts.google_tts import GoogleTTS
            log(f"Creating Google TTS with model {model} (multi_speaker={multi_speaker})")
            return GoogleTTS(model=model, multi_speaker=multi_speaker)
        elif provider == "csm":
            from audible.tts.csm_tts import CSMTTS
            log(f"Creating CSM TTS with model {model}")
            return CSMTTS(model=model)
        else:
            log(f"Unknown TTS provider: {provider}", level="ERROR")
            raise ValueError(f"Unknown TTS provider: {provider}. Supported providers: openai, cartesia, google, csm")
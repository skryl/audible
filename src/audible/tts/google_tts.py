"""
Google Cloud TTS provider implementation.
"""

import os
import json
from google.cloud import texttospeech
from google.oauth2 import service_account
from audible.utils.common import log

class GoogleTTS:
    """Class for interacting with Google Cloud text-to-speech API."""

    def __init__(self, model="en-US-Neural2-D"):
        """
        Initialize Google Cloud TTS provider.

        Args:
            model: Google TTS voice model to use
        """
        self.model = model
        self.client = self._initialize_client()
        log(f"Initialized Google Cloud TTS with voice model {model}")

    def _initialize_client(self):
        """Initialize the Google Cloud TTS client."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

        try:
            if os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                client = texttospeech.TextToSpeechClient(credentials=credentials)
                log(f"Initialized Google Cloud TTS client using credentials from {credentials_path}")
            else:
                # Fall back to application default credentials
                client = texttospeech.TextToSpeechClient()
                log("Initialized Google Cloud TTS client using application default credentials")
            return client
        except Exception as e:
            log(f"Error initializing Google Cloud TTS client: {e}", level="ERROR")
            raise

    def generate_speech(self, request):
        """
        Generate speech using Google Cloud TTS API.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use (optional, uses model from constructor if not provided)
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply (mapped to speaking rate and pitch)
                - language_code: Optional language code (defaults to en-US)

        Returns:
            Path to the generated audio file or None if failed
        """
        text = request.get("text", "")
        voice_id = request.get("voice_id", self.model)
        output_file = request.get("output_file", "")
        emotion = request.get("emotion")
        language_code = request.get("language_code", "en-US")

        if not text or not output_file:
            log("Missing required parameters for TTS request", level="ERROR")
            return None

        log(f"Generating speech for text: {text[:50]}...")

        try:
            # Set the text input to be synthesized
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Build the voice request
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_id
            )

            # Set the audio file type
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            # Apply emotion via prosody if specified
            if emotion and os.getenv("AUDIBLE_NO_EMOTIONS", "").lower() != "true":
                # Map emotions to speaking rate and pitch modifications
                emotion_mapping = {
                    "happy": {"rate": 1.1, "pitch": 2.0},
                    "sad": {"rate": 0.9, "pitch": -2.0},
                    "angry": {"rate": 1.2, "pitch": 1.0},
                    "fearful": {"rate": 1.3, "pitch": 3.0},
                    "excited": {"rate": 1.3, "pitch": 4.0},
                    "serious": {"rate": 0.9, "pitch": -1.0},
                    "urgent": {"rate": 1.4, "pitch": 1.0}
                }

                # Get emotion parameters or use defaults for unknown emotions
                emotion_params = emotion_mapping.get(emotion.lower(), {"rate": 1.0, "pitch": 0.0})

                # Apply SSML with prosody
                ssml_text = f"""
                <speak>
                  <prosody rate="{emotion_params['rate']}" pitch="{emotion_params['pitch']}st">
                    {text}
                  </prosody>
                </speak>
                """

                # Update the synthesis input to use SSML
                synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)

            # Perform the text-to-speech request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )

            # Save the audio file
            with open(output_file, "wb") as out:
                out.write(response.audio_content)

            log(f"Saved audio to {output_file}")
            return output_file

        except Exception as e:
            log(f"Error generating speech with Google Cloud TTS: {e}", level="ERROR")
            return None

    def list_voices(self, language_code="en-US", gender=None):
        """
        List available voices from Google Cloud TTS.

        Args:
            language_code: Filter by language code
            gender: Filter by gender (MALE, FEMALE, NEUTRAL)

        Returns:
            List of voice dictionaries
        """
        try:
            # List all available voices
            response = self.client.list_voices(language_code=language_code)

            # Apply filters and format the results
            filtered_voices = []
            for voice in response.voices:
                # Skip if language doesn't match
                if language_code and language_code not in voice.language_codes:
                    continue

                # Apply gender filter if specified
                if gender:
                    gender_match = False
                    for voice_gender in voice.ssml_gender:
                        if gender.upper() == str(voice_gender):
                            gender_match = True
                            break
                    if not gender_match:
                        continue

                # Add the voice to the filtered list
                filtered_voices.append({
                    "id": voice.name,
                    "name": voice.name,
                    "language_codes": voice.language_codes,
                    "gender": str(voice.ssml_gender),
                    "sample_rate_hertz": voice.natural_sample_rate_hertz
                })

            return filtered_voices

        except Exception as e:
            log(f"Error listing Google Cloud TTS voices: {e}", level="ERROR")
            return []
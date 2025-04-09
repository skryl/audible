"""
Cartesia TTS provider implementation.
"""

import os
import json
import asyncio
from cartesia import Cartesia, AsyncCartesia
from audible.utils.common import log, prepare_chapter_directory

class CartesiaTTS:
    """Class for interacting with Cartesia text-to-speech API."""

    def __init__(self, model="sonic-2", use_cloned_voices=False):
        """
        Initialize Cartesia TTS provider.

        Args:
            model: Cartesia model to use
            use_cloned_voices: Whether to use cloned voices when available
        """
        self.model = model
        self.use_cloned_voices = use_cloned_voices
        self.client = Cartesia(api_key=os.getenv("CARTESIA_API_KEY"))
        self.async_client = AsyncCartesia(api_key=os.getenv("CARTESIA_API_KEY"))
        log(f"Initialized Cartesia TTS with model {model} (use_cloned_voices={use_cloned_voices})")

    def _prepare_tts_params(self, request, is_async=False):
        """
        Prepare common parameters for Cartesia TTS API calls.

        Args:
            request: Dictionary containing the TTS request details
            is_async: Whether this is for an async call

        Returns:
            tuple: (text, voice_id, voice_config, output_file) or None if missing required params
        """
        text = request.get("text", "")
        voice_id = request.get("voice_id", "")
        output_file = request.get("output_file", "")
        emotion = request.get("emotion")
        voice_traits = request.get("voice_traits")

        if not text or not output_file:
            log("Missing required parameters for TTS request", level="ERROR")
            return None

        if not voice_id:
            speaker = request.get("character_name", "Unknown")
            log(f"Missing voice_id for character '{speaker}' with text: {text[:50]}...", level="ERROR")
            log("Make sure voice_mappings.json has valid 'cartesia' voice IDs for all characters", level="ERROR")
            return None
        
        # Log context for different execution modes
        if is_async:
            log(f"Generating speech async for text: {text[:50]}...")
        else:
            log(f"Generating speech for text: {text[:50]}...")

        # Prepare voice parameters with experimental controls
        voice = {
            "mode": "id",
            "id": voice_id,
            "__experimental_controls": {
                "speed": "normal"
            }
        }

        # Add detailed DEBUG log for voice ID
        log(f"Using Cartesia voice ID: {voice_id} for text segment", level="DEBUG")

        # Add emotion if specified using the experimental controls format
        if emotion:
            # Format emotion(s) as a list
            emotion_list = []

            # Handle different emotion formats
            if ":" in emotion:
                # Already formatted like "positivity:high"
                emotion_list.append(emotion)
            elif emotion.lower() != "neutral":
                # Simple emotion name, no intensity specified
                emotion_list.append(emotion)

            # Turn off emotions for now until Cartesia supports them
            if False and emotion_list:
                voice["__experimental_controls"]["emotion"] = emotion_list
                log(f"Using emotions: {emotion_list}")

        # Common API parameters for both sync and async calls
        api_params = {
            "model_id": self.model,
            "transcript": text,
            "voice": voice,
            "language": "en",
            "output_format": {
                "container": "mp3",
                "sample_rate": 44100,
            }
        }

        return text, voice_id, output_file, api_params

    def generate_speech(self, request):
        """
        Generate speech using Cartesia API.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use (should be fully determined in TTS preparation)
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply
                - voice_traits: Optional voice characteristics to apply

        Returns:
            Path to the generated audio file or None if failed
        """
        result = self._prepare_tts_params(request, is_async=False)
        if result is None:
            return None

        text, voice_id, output_file, api_params = result

        try:
            # The response is a generator, so we need to consume it
            audio_data = bytes()

            for chunk in self.client.tts.bytes(**api_params):
                audio_data += chunk

            # Save the audio file
            with open(output_file, 'wb') as f:
                f.write(audio_data)

            log(f"Saved audio to {output_file}")
            return output_file

        except Exception as e:
            log(f"Error generating speech with Cartesia: {e}", level="ERROR")
            return None

    async def generate_speech_async(self, request):
        """
        Generate speech using Cartesia API asynchronously.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use (should be fully determined in TTS preparation)
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply
                - voice_traits: Optional voice characteristics to apply

        Returns:
            Path to the generated audio file or None if failed
        """
        result = self._prepare_tts_params(request, is_async=True)
        if result is None:
            return None

        text, voice_id, output_file, api_params = result

        try:
            # Get audio data asynchronously - use bytes() method instead of generate()
            audio_chunks = []
            async for chunk in self.async_client.tts.bytes(**api_params):
                audio_chunks.append(chunk)
                
            # Combine all chunks into one audio data
            audio_data = b''.join(audio_chunks)

            # Save the audio file
            with open(output_file, 'wb') as f:
                f.write(audio_data)

            log(f"Saved audio to {output_file}")
            return output_file

        except Exception as e:
            log(f"Error generating speech with Cartesia async: {e}", level="ERROR")
            return None

    def _get_cloned_voice_id(self, character_name):
        """
        Get the cloned voice ID for a character if available.

        Args:
            character_name: Name of the character

        Returns:
            Cloned voice ID or None if not found
        """
        try:
            # Normalize character name for filename
            safe_name = character_name.replace(' ', '_').replace("'", "").replace('"', "").lower()

            # Check if a cloned voice mapping exists
            cloned_voices_file = os.path.join(os.getcwd(), "cloned_voices.json")
            if os.path.exists(cloned_voices_file):
                with open(cloned_voices_file, 'r', encoding='utf-8') as f:
                    cloned_voices = json.load(f)

                if character_name in cloned_voices:
                    return cloned_voices[character_name]

                # Try case-insensitive matching
                for name, voice_id in cloned_voices.items():
                    if name.lower() == character_name.lower():
                        return voice_id

            log(f"No cloned voice found for character {character_name}")
            return None

        except Exception as e:
            log(f"Error getting cloned voice ID: {e}", level="ERROR")
            return None

    def _prepare_chapter_directory(self, output_path):
        """
        Create chapter directory structure and return necessary paths.

        Args:
            output_path: Original output path for the audio file

        Returns:
            tuple: (chapter_dir, new_output_path, chapter_name)
        """
        return prepare_chapter_directory(output_path)

    def _prepare_segment_request(self, segment, index, chapter_dir):
        """
        Prepare a request for a single speech segment.

        Args:
            segment: A single segment from the TTS request
            index: Index of the segment in the segments list
            chapter_dir: Directory to save segment files

        Returns:
            tuple: (request_dict, temp_output_path)
        """
        segment_type = segment.get("type", "narration")
        text = segment.get("text", "")

        # Skip empty segments
        if not text.strip():
            return None, None

        # Get voice ID based on segment type
        voice_id = segment.get("voice_id", "")

        # Debug voice ID issues upfront
        if not voice_id:
            speaker = segment.get("character", "") if segment_type == "dialogue" else "Narrator"
            log(f"Segment {index}: Missing voice_id for '{speaker}' - this will cause an error", level="WARNING")

        # Get emotion if available
        emotion = segment.get("emotion", "neutral") if segment_type == "dialogue" else None

        # Get character name for potential cloned voice
        character = segment.get("character", "") if segment_type == "dialogue" else ""

        # Get voice characteristics if available
        voice_traits = segment.get("voice_traits")

        # Create segment output file in the chapter directory with descriptive name
        segment_name = f"segment_{index:04d}"
        temp_output = os.path.join(chapter_dir, f"{segment_name}.mp3")

        # Create request for this segment
        request = {
            "text": text,
            "voice_id": voice_id,
            "output_file": temp_output,
            "character_name": character,
            "emotion": emotion,
            "voice_traits": voice_traits
        }

        return request, temp_output

    def _combine_audio_files(self, audio_files, new_output_path, chapter_dir, chapter_name):
        """
        Combine multiple audio files into a single output file.

        Args:
            audio_files: List of audio file paths to combine
            new_output_path: Path to save the combined audio file
            chapter_dir: Directory where chapter files are stored
            chapter_name: Name of the chapter

        Returns:
            bool: True if successful, False otherwise
        """
        if len(audio_files) == 1:
            # If only one file, just copy it (don't delete original)
            import shutil
            shutil.copy(audio_files[0], new_output_path)
            log(f"Single segment file saved as: {new_output_path}")
            return True
        else:
            # Combine multiple files
            # This requires ffmpeg to be installed
            import subprocess

            # Create file list for ffmpeg
            list_file = os.path.join(chapter_dir, f"{chapter_name}.list")
            with open(list_file, "w") as f:
                for temp_file in audio_files:
                    # Use absolute paths to prevent path resolution issues
                    abs_path = os.path.abspath(temp_file)
                    f.write(f"file '{abs_path}'\n")

            # Run ffmpeg to concatenate files
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_file, "-c", "copy", new_output_path
            ]

            process = subprocess.run(cmd, capture_output=True, text=True)

            if process.returncode != 0:
                log(f"Error combining audio files: {process.stderr}", level="ERROR")
                return False

            # Keep the list file for reference
            log(f"Merged {len(audio_files)} segment files into: {new_output_path}")
            log(f"Segment files are preserved in: {chapter_dir}")
            return True

    def generate_audio_from_request(self, tts_request, output_path):
        """
        Generate audio from a TTS request and save to file.
        Creates a chapter-specific directory and preserves all segment audio files within it.

        Args:
            tts_request: Dictionary with TTS request information
            output_path: Path to save the audio file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Process segments in the TTS request
            segments = tts_request.get("segments", [])

            if not segments:
                log("No segments found in TTS request", level="ERROR")
                return False

            # Create chapter directory and get paths
            chapter_dir, new_output_path, chapter_name = self._prepare_chapter_directory(output_path)

            # Process each segment sequentially
            temp_files = []
            for i, segment in enumerate(segments):
                request, temp_output = self._prepare_segment_request(segment, i, chapter_dir)
                
                if request is None:  # Skip empty segments
                    continue
                    
                result = self.generate_speech(request)
                if result:
                    temp_files.append(temp_output)

            # If no segments were processed successfully, fail
            if not temp_files:
                log("No segments were processed successfully", level="ERROR")
                return False

            # Combine all temporary files into one
            if not self._combine_audio_files(temp_files, new_output_path, chapter_dir, chapter_name):
                return False

            log(f"Generated audio files stored in {chapter_dir}")
            log(f"All {len(temp_files)} segment files are preserved in this directory")
            return True

        except Exception as e:
            log(f"Error generating audio from request: {e}", level="ERROR")
            return False

    async def generate_audio_from_request_async(self, tts_request, output_path):
        """
        Generate audio from a TTS request and save to file using async processing.
        Creates a chapter-specific directory and preserves all segment audio files within it.

        Args:
            tts_request: Dictionary with TTS request information
            output_path: Path to save the audio file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Process segments in the TTS request
            segments = tts_request.get("segments", [])

            if not segments:
                log("No segments found in TTS request", level="ERROR")
                return False

            # Create chapter directory and get paths
            chapter_dir, new_output_path, chapter_name = self._prepare_chapter_directory(output_path)

            # Prepare requests for all segments
            temp_files = []
            requests = []

            for i, segment in enumerate(segments):
                request, temp_output = self._prepare_segment_request(segment, i, chapter_dir)
                
                if request is None:  # Skip empty segments
                    continue
                    
                requests.append(request)
                temp_files.append(temp_output)

            # Process requests in parallel (with concurrency limit)
            MAX_CONCURRENT = 5
            semaphore = asyncio.Semaphore(MAX_CONCURRENT)

            async def process_with_semaphore(request):
                async with semaphore:
                    return await self.generate_speech_async(request)

            # Create tasks for all requests
            tasks = [process_with_semaphore(request) for request in requests]

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out failed requests
            successful_files = []
            for i, result in enumerate(results):
                if isinstance(result, str) and os.path.exists(temp_files[i]):
                    successful_files.append(temp_files[i])
                elif isinstance(result, Exception):
                    log(f"Error processing segment {i}: {result}", level="ERROR")

            # If no segments were processed successfully, fail
            if not successful_files:
                log("No segments were processed successfully", level="ERROR")
                return False

            # Combine all temporary files into one
            if not self._combine_audio_files(successful_files, new_output_path, chapter_dir, chapter_name):
                return False

            log(f"Generated audio files stored in {chapter_dir}")
            log(f"All {len(successful_files)} segment files are preserved in this directory")
            return True

        except Exception as e:
            log(f"Error generating audio from request (async): {e}", level="ERROR")
            return False

    def list_voices(self, gender=None, age=None, accent=None):
        """
        List available voices from Cartesia.

        Args:
            gender: Filter by gender (male, female)
            age: Filter by age (child, young, middle_aged, elderly)
            accent: Filter by accent (british, american, etc.)

        Returns:
            List of voice dictionaries
        """
        try:
            response = self.client.voices.list()
            voices = response.voices

            # Apply filters if specified
            filtered_voices = []
            for voice in voices:
                # Apply gender filter
                if gender and voice.tags.gender != gender:
                    continue

                # Apply age filter
                if age and voice.tags.age != age:
                    continue

                # Apply accent filter
                if accent and voice.tags.accent != accent:
                    continue

                filtered_voices.append({
                    "id": voice.id,
                    "name": voice.name,
                    "gender": voice.tags.gender,
                    "age": voice.tags.age,
                    "accent": voice.tags.accent
                })

            return filtered_voices

        except Exception as e:
            log(f"Error listing Cartesia voices: {e}", level="ERROR")
            return []

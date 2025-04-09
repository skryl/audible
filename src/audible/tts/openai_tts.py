"""
OpenAI TTS module for generating speech from text.
"""

import os
import json
import time
import asyncio
from openai import OpenAI, AsyncOpenAI
from audible.utils.common import log, prepare_chapter_directory

class OpenAITTS:
    """Class for interacting with OpenAI text-to-speech API."""

    def __init__(self, model="gpt-4o-mini-tts"):
        """
        Initialize OpenAI TTS provider.

        Args:
            model: OpenAI TTS model to use
        """
        self.model = model
        self.client = OpenAI()  # Assumes API key is in environment variable OPENAI_API_KEY
        self.async_client = AsyncOpenAI()  # Async client
        log(f"Initialized OpenAI TTS with model {model}")

    def _prepare_tts_params(self, request):
        """
        Prepare common parameters for TTS API calls.

        Args:
            request: Dictionary containing the TTS request details

        Returns:
            Tuple containing (text, voice_id, instructions, output_file) or None if missing required params
        """

        text = request.get("text", "")
        voice_id = request.get("voice_id", "onyx")  # Default to onyx voice
        output_file = request.get("output_file", "")
        emotion = request.get("emotion")
        voice_traits = request.get("voice_traits")
        character_voice_traits = request.get("character_voice_traits")


        if not text or not output_file:
            log("Missing required parameters for TTS request", level="ERROR")
            return None

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        if not voice_id:
            log(f"No voice ID specified for text: {text[:50]}...", level="ERROR")
            return None

        # Prepare voice instructions
        voice_instructions = []

        # Add emotion if provided
        if emotion:
            voice_instructions.append(f"Emotion: {emotion}")

        # Add voice characteristics if provided
        if voice_traits:
            voice_instructions.append(" | ")
            voice_instructions.append(f"Voice Characteristics: {voice_traits}")
        if character_voice_traits:
            voice_instructions.append(" | ")
            voice_instructions.append(f"Character Idiolect: {character_voice_traits}")

        # Combine voice instructions for the instructions parameter
        instructions = ". ".join(voice_instructions) if voice_instructions else None

        # Build API params
        api_params = {
            "model": self.model,
            "voice": voice_id,
            "input": text,
        }

        if instructions:
            api_params["instructions"] = instructions

        return api_params, output_file, text

    def generate_speech(self, request):
        """
        Generate speech using OpenAI API.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply
                - voice_traits: Optional voice characteristics to apply

        Returns:
            Path to the generated audio file or None if failed
        """
        # Prepare common parameters
        result = self._prepare_tts_params(request)
        if result is None:
            return None

        api_params, output_file, text = result

        log(f"Generating speech for text: {text[:50]}...")

        try:
            # Call the OpenAI TTS API
            response = self.client.audio.speech.create(**api_params)

            # Save the audio file
            response.stream_to_file(output_file)
            log(f"Saved audio to {output_file}")
            return output_file

        except Exception as e:
            log(f"Error generating speech with OpenAI: {e}", level="ERROR")
            return None

    async def generate_speech_async(self, request):
        """
        Generate speech using OpenAI API asynchronously.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply
                - voice_traits: Optional voice characteristics to apply

        Returns:
            Path to the generated audio file or None if failed
        """
        # Prepare common parameters
        result = self._prepare_tts_params(request)
        if result is None:
            return None

        api_params, output_file, text = result

        log(f"Generating speech async for text: {text[:50]}...")

        try:
            # Call the OpenAI TTS API asynchronously
            response = await self.async_client.audio.speech.create(**api_params)

            # Save the audio file - this still happens synchronously
            with open(output_file, "wb") as file:
                file.write(response.content)

            log(f"Saved audio to {output_file}")
            return output_file

        except Exception as e:
            log(f"Error generating speech with OpenAI async: {e}", level="ERROR")
            return None

    def _prepare_chapter_directory(self, output_path):
        """
        Create the chapter directory structure and return necessary paths.
        
        Args:
            output_path: The original output path for the audio file
            
        Returns:
            tuple: (chapter_dir, new_output_path, chapter_name)
        """
        return prepare_chapter_directory(output_path)
    
    def _prepare_segment_request(self, segment, index, chapter_dir):
        """
        Prepare a request for a single speech segment.
        
        Args:
            segment: The segment data dictionary
            index: The segment index
            chapter_dir: The chapter directory path
            
        Returns:
            tuple: (request_dict, temp_output_path) or (None, None) if segment should be skipped
        """
        segment_type = segment.get("type", "narration")
        text = segment.get("text", "")
        
        # Skip empty segments
        if not text.strip():
            return None, None
        
        # Get voice ID and parameters
        voice_id = segment.get("voice_id", "onyx")
        emotion = segment.get("emotion", "neutral") if segment_type == "dialogue" else None
        voice_traits = segment.get("voice_traits")
        
        # Create segment filename
        segment_name = f"segment_{index:04d}"
        if segment.get("speaker"):
            speaker = segment.get("speaker").replace(" ", "_").lower()
            segment_name += f"_{speaker}"
        
        temp_output = os.path.join(chapter_dir, f"{segment_name}.mp3")
        
        # Create request dictionary
        request = {
            "text": text,
            "voice_id": voice_id,
            "output_file": temp_output,
            "emotion": emotion,
            "voice_traits": voice_traits
        }
        
        return request, temp_output
    
    def _combine_audio_files(self, files, new_output_path, chapter_dir, chapter_name):
        """
        Combine multiple audio files into a single output file.
        
        Args:
            files: List of audio file paths to combine
            new_output_path: The final output path
            chapter_dir: The chapter directory path
            chapter_name: The chapter name for the list file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if len(files) == 1:
            # If only one file, just copy it
            import shutil
            shutil.copy(files[0], new_output_path)
            log(f"Single segment file saved as: {new_output_path}")
            return True
        
        # Combine multiple files using ffmpeg
        import subprocess
        
        # Create file list for ffmpeg
        list_file = os.path.join(chapter_dir, f"{chapter_name}.list")
        with open(list_file, "w") as f:
            for temp_file in files:
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
        
        # Log success
        log(f"Merged {len(files)} segment files into: {new_output_path}")
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

            # Create directory structure
            chapter_dir, new_output_path, chapter_name = self._prepare_chapter_directory(output_path)
            
            # Process each segment sequentially
            temp_files = []
            for i, segment in enumerate(segments):
                request, temp_output = self._prepare_segment_request(segment, i, chapter_dir)
                if not request:
                    continue
                    
                result = self.generate_speech(request)
                if result:
                    temp_files.append(temp_output)

            # If no segments were processed successfully, fail
            if not temp_files:
                log("No segments were processed successfully", level="ERROR")
                return False

            # Combine audio files
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

            # Create directory structure
            chapter_dir, new_output_path, chapter_name = self._prepare_chapter_directory(output_path)
            
            # Prepare requests for all segments
            temp_files = []
            requests = []

            for i, segment in enumerate(segments):
                request, temp_output = self._prepare_segment_request(segment, i, chapter_dir)
                if not request:
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

            # Combine audio files
            if not self._combine_audio_files(successful_files, new_output_path, chapter_dir, chapter_name):
                return False

            log(f"Generated audio files stored in {chapter_dir}")
            log(f"All {len(successful_files)} segment files are preserved in this directory")
            return True

        except Exception as e:
            log(f"Error generating audio from request (async): {e}", level="ERROR")
            return False

    def list_voices(self):
        """
        List available voices from OpenAI.

        Returns:
            List of voice identifiers
        """
        # OpenAI has a fixed set of voices
        return [
            {"id": "alloy", "name": "Alloy", "gender": "neutral", "description": "Versatile, neutral voice"},
            {"id": "echo", "name": "Echo", "gender": "male", "description": "Male voice with depth"},
            {"id": "fable", "name": "Fable", "gender": "female", "description": "Versatile female voice"},
            {"id": "onyx", "name": "Onyx", "gender": "male", "description": "Deep male voice"},
            {"id": "nova", "name": "Nova", "gender": "female", "description": "Bright female voice"},
            {"id": "shimmer", "name": "Shimmer", "gender": "female", "description": "Warm female voice"}
        ]

# Keep the utility functions for backward compatibility

def extract_emotional_cues(text):
    """Extract emotional cues from text in parentheses or brackets."""
    # Extract text in parentheses
    import re
    parentheses_pattern = r'\(([^)]*)\)'
    brackets_pattern = r'\[([^\]]*)\]'

    # Find all matches
    parentheses_matches = re.findall(parentheses_pattern, text)
    brackets_matches = re.findall(brackets_pattern, text)

    # Combine all matches
    all_matches = parentheses_matches + brackets_matches

    # Join with commas
    if all_matches:
        return ", ".join(all_matches)
    else:
        return ""
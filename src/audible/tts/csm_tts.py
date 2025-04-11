"""
CSM TTS module for generating speech using local CSM ML models.
"""

import os
import time
from audible.utils.common import log, prepare_chapter_directory
from huggingface_hub import hf_hub_download
import numpy as np
import soundfile as sf

from csm_mlx import CSM, csm_1b, generate, Segment
import mlx.core as mx


class CSMTTS:
    """Class for generating speech using local CSM MLX models."""

    def __init__(self, model="csm-1b"):
        """
        Initialize CSM TTS provider.

        Args:
            model: CSM model identifier (default: csm-1b)
        """
        self.model = model
        self._initialize_model()
        log(f"Initialized CSM TTS with model {model}")

    def _initialize_model(self):
        """Initialize the CSM model. Downloads weights if needed."""
        try:
            # Initialize the model
            self.csm = CSM(csm_1b())

            # Define repo_id based on the model
            if self.model == "csm-1b":
                repo_id = "senstella/csm-1b-mlx"
            else:
                repo_id = f"senstella/{self.model}-mlx"

            weight_path = hf_hub_download(repo_id=repo_id, filename="ckpt.safetensors")
            self.csm.load_weights(weight_path)
            log(f"Loaded CSM model weights from {weight_path}")
            return True
        except Exception as e:
            log(f"Error initializing CSM model: {e}", level="ERROR")
            return False

    def _prepare_tts_params(self, request):
        """
        Prepare common parameters for TTS API calls.

        Args:
            request: Dictionary containing the TTS request details

        Returns:
            Tuple containing (text, voice_id, output_file) or None if missing required params
        """
        text = request.get("text", "")
        voice_id = request.get("voice_id", "default")  # Default voice ID
        output_file = request.get("output_file", "")
        emotion = request.get("emotion")

        if not text or not output_file:
            log("Missing required parameters for TTS request", level="ERROR")
            return None

        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Prepare context instructions for metadata only
        context_instructions = []

        # Add emotion if provided
        if emotion and emotion != "neutral":
            context_instructions.append(f"Speaking with {emotion} emotion.")

        # Add voice characteristics if provided
        if request.get("voice_traits"):
            context_instructions.append(f"Voice characteristics: {request.get('voice_traits')}")

        if request.get("character_voice_traits"):
            context_instructions.append(f"Character voice traits: {request.get('character_voice_traits')}")

        context_prompt = ". ".join(context_instructions) if context_instructions else None

        return {
            "text": text,
            "voice_id": voice_id,
            "output_file": output_file,
            "context_prompt": context_prompt
        }

    def generate_speech(self, request, context_segments=None):
        """
        Generate speech using the local CSM model.

        Args:
            request: Dictionary containing the TTS request details:
                - text: The text to convert to speech
                - voice_id: The voice ID to use
                - output_file: Path to save the audio file
                - emotion: Optional emotion to apply
                - voice_traits: Optional voice characteristics to apply
            context_segments: List of previously generated Segment objects for context

        Returns:
            Path to the generated audio file or None if failed
        """
        params = self._prepare_tts_params(request)
        if not params:
            return None

        text = params["text"]
        voice_id = params["voice_id"]
        output_file = params["output_file"]
        context_prompt = params["context_prompt"]

        log(f"Generating speech for text: {text[:50]}...")

        try:
            # Map the voice_id to a speaker ID (0-5 range for CSM model)
            # We'll use a simple hash function to map voice_id strings to integers
            speaker_id = hash(voice_id) % 6  # Use 6 different possible speakers

            # Use provided context segments if available
            context = context_segments or []

            # Generate audio using CSM
            audio = generate(
                self.csm,
                text=text,
                speaker=speaker_id,
                context=context,
                max_audio_length_ms=100_000  # 100 seconds max
            )

            # Save the audio file (CSM generates float32 arrays at 24kHz)
            sf.write(output_file, audio, 24000, format='WAV')
            log(f"Saved audio to {output_file}")

            # Create and return a new segment with this generated audio
            new_segment = Segment(
                speaker=speaker_id,
                text=text,
                audio=mx.array(audio, dtype=mx.float32)
            )

            return output_file, new_segment

        except Exception as e:
            log(f"Error generating speech with CSM: {e}", level="ERROR")
            return None, None

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
        voice_id = segment.get("voice_id", "default")
        emotion = segment.get("emotion", "neutral") if segment_type == "dialogue" else None
        voice_traits = segment.get("voice_traits")

        # Create segment filename
        segment_name = f"segment_{index:04d}"
        if segment.get("speaker"):
            speaker = segment.get("speaker").replace(" ", "_").lower()
            segment_name += f"_{speaker}"

        temp_output = os.path.join(chapter_dir, f"{segment_name}.wav")

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

            # Process each segment sequentially, building context as we go
            temp_files = []
            context_segments = []  # Keep track of all previously generated segments

            for i, segment in enumerate(segments):
                request, temp_output = self._prepare_segment_request(segment, i, chapter_dir)
                if not request:
                    continue

                # Generate speech with context from previous segments
                result, new_segment = self.generate_speech(request, context_segments)
                if result:
                    temp_files.append(temp_output)
                    if new_segment:
                        # Add this segment to the context for future generations
                        context_segments.append(new_segment)

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


    def list_voices(self):
        """
        List available voices from CSM.

        Returns:
            List of voice identifiers
        """
        # For CSM, voices are speaker identifiers (0-5)
        return [
            {"id": "speaker_0", "name": "Speaker 0", "gender": "neutral", "description": "CSM default speaker 0"},
            {"id": "speaker_1", "name": "Speaker 1", "gender": "masculine", "description": "CSM masculine voice"},
            {"id": "speaker_2", "name": "Speaker 2", "gender": "feminine", "description": "CSM feminine voice"},
            {"id": "speaker_3", "name": "Speaker 3", "gender": "neutral", "description": "CSM neutral voice"},
            {"id": "speaker_4", "name": "Speaker 4", "gender": "masculine", "description": "CSM deeper masculine voice"},
            {"id": "speaker_5", "name": "Speaker 5", "gender": "feminine", "description": "CSM higher feminine voice"}
        ]
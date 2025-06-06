"""
Google Gemini TTS provider implementation.
"""

import os
import json
import wave
import base64
import asyncio
import time
from google import genai
from google.genai import types
from audible.utils.common import log
from audible.utils.thread_pool import process_batch_async

class GoogleTTS:
    """Class for interacting with Google Gemini text-to-speech API."""

    def __init__(self, model="gemini-2.5-flash-preview-tts"):
        """
        Initialize Google Gemini TTS provider.

        Args:
            model: Google TTS model to use
        """
        self.model = model
        self.client = self._initialize_client()
        self.last_request_time = 0
        self.request_delay = 20.0  # 20 seconds between requests to stay under 3/minute quota
        log(f"Initialized Google Gemini TTS with model {model}")

    def _initialize_client(self):
        """Initialize the Gemini client."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            # Try to get from GEMINI_API_KEY as fallback
            api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            log("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment variables", level="ERROR")
            raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is required for Google provider")

        try:
            client = genai.Client(api_key=api_key)
            log(f"Initialized Google Gemini client")

            # Try to get project information by making a simple request
            try:
                # Make a minimal request to get project info
                test_response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents="Return just the word 'test'",
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT"],
                        max_output_tokens=10
                    )
                )
                log("Successfully authenticated with Gemini API")

                # Parse the API key to extract project info (if possible)
                # API keys typically contain project identifiers
                if api_key.startswith("AIza"):
                    log(f"Using API key: {api_key[:10]}...{api_key[-4:]}")
                    log("Note: To check if this is a paid tier key, visit https://aistudio.google.com/app/apikey")
                    log("Look for 'Paid' or 'Free' next to your project name")

            except Exception as auth_e:
                if "RESOURCE_EXHAUSTED" in str(auth_e):
                    log("API key is valid but hitting rate limits (possible free tier)", level="WARNING")
                    log(f"Rate limit error: {auth_e}", level="WARNING")
                elif "INVALID_ARGUMENT" in str(auth_e):
                    log("API key is valid but request failed", level="WARNING")
                else:
                    log(f"Authentication test warning: {auth_e}", level="WARNING")

            return client
        except Exception as e:
            log(f"Error initializing Google Gemini client: {e}", level="ERROR")
            raise

    def _save_wave_file(self, filename, pcm_data, channels=1, rate=24000, sample_width=2):
        """Save PCM data as a wave file."""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)

    def _rate_limit(self):
        """Apply rate limiting to stay under API quota."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.request_delay:
            sleep_time = self.request_delay - time_since_last_request
            log(f"Rate limiting: waiting {sleep_time:.1f} seconds before next API call")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _generate_single_speaker_audio(self, text, voice_id):
        """Generate audio using single-speaker mode."""
        # self._rate_limit()
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_id,
                            )
                        )
                    ),
                )
            )

            # Extract audio data from response
            data = response.candidates[0].content.parts[0].inline_data.data
            return data
        except Exception as e:
            log(f"Error generating single-speaker audio: {e}", level="ERROR")
            return None

    def _group_segments_by_speaker_pairs(self, segments):
        """
        Group segments into chunks that can be processed with 2-speaker multi-speaker mode.
        Tries to create balanced groups where both speakers actually have dialogue.
        Never groups Narrator with other speakers.
        """
        groups = []
        current_group = []
        current_speakers = {}
        speaker_segment_count = {}  # Track how many segments each speaker has

        # First pass: identify all speakers and their segment counts
        all_speakers = {}
        for segment in segments:
            if segment.get("type") == "dialogue":
                speaker = segment.get("character", "Narrator")
                voice_id = segment.get("voice_id", "Charon")
            else:
                speaker = "Narrator"
                voice_id = segment.get("voice_id", "Charon")

            if speaker not in all_speakers:
                all_speakers[speaker] = voice_id

        log(f"Found {len(all_speakers)} unique speakers in {len(segments)} segments")

        for i, segment in enumerate(segments):
            # Determine the speaker for this segment
            if segment.get("type") == "dialogue":
                speaker = segment.get("character", "Narrator")
                voice_id = segment.get("voice_id", "Charon")
            else:
                speaker = "Narrator"
                voice_id = segment.get("voice_id", "Charon")

            # Check if we need to start a new group
            should_start_new_group = False

            # Special handling for Narrator - never mix with other speakers
            if speaker == "Narrator" and len(current_speakers) > 0 and "Narrator" not in current_speakers:
                # Narrator segment but current group has non-narrator speakers
                should_start_new_group = True
            elif speaker != "Narrator" and "Narrator" in current_speakers:
                # Non-narrator segment but current group has narrator
                should_start_new_group = True
            elif speaker not in current_speakers and len(current_speakers) >= 2:
                # Would exceed 2 speakers
                should_start_new_group = True
            elif len(current_group) > 10 and len(current_speakers) == 2:
                # Group is getting too long with 2 speakers
                should_start_new_group = True
            elif speaker in current_speakers and len(current_speakers) == 1 and len(current_group) > 5:
                # Single speaker group is getting too long, look ahead for dialogue
                # Check if there's dialogue coming up soon
                for j in range(i + 1, min(i + 5, len(segments))):
                    future_segment = segments[j]
                    if future_segment.get("type") == "dialogue":
                        future_speaker = future_segment.get("character", "Narrator")
                        if future_speaker != speaker:
                            # Different speaker coming up, start new group now
                            should_start_new_group = True
                            break

            if should_start_new_group:
                # Save current group if it has segments
                if current_group:
                    # Only create group if it has meaningful content
                    if len(current_speakers) == 2 or len(current_group) >= 3:
                        groups.append({
                            "segments": current_group,
                            "speakers": current_speakers.copy()
                        })
                        log(f"Created group {len(groups)} with {len(current_speakers)} speakers: {list(current_speakers.keys())} ({len(current_group)} segments)")

                # Start new group
                current_group = []
                current_speakers = {}
                speaker_segment_count = {}

            # Add speaker to current group
            if speaker not in current_speakers:
                current_speakers[speaker] = voice_id
                speaker_segment_count[speaker] = 0

            speaker_segment_count[speaker] += 1
            current_group.append(segment)

        # Don't forget the last group
        if current_group and (len(current_speakers) == 2 or len(current_group) >= 3):
            groups.append({
                "segments": current_group,
                "speakers": current_speakers
            })
            log(f"Created final group {len(groups)} with {len(current_speakers)} speakers: {list(current_speakers.keys())} ({len(current_group)} segments)")

        return groups

    def _generate_multi_speaker_audio_for_group(self, segments, speakers):
        """Generate audio for a group of segments with up to 2 speakers."""
        speaker_configs = []
        prompt_parts = []

        # Build speaker voice configs
        for speaker_name, voice_id in speakers.items():
            speaker_configs.append(
                types.SpeakerVoiceConfig(
                    speaker=speaker_name,
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_id,
                        )
                    )
                )
            )

        # Build the prompt with speaker annotations
        for segment in segments:
            text = segment.get("text", "")
            if segment.get("type") == "dialogue":
                character = segment.get("character", "Narrator")
                prompt_parts.append(f"{character}: {text}")
            else:
                prompt_parts.append(f"Narrator: {text}")

        # Combine all text
        full_prompt = "TTS the following conversation:\n" + "\n".join(prompt_parts)

        # self._rate_limit()
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=speaker_configs
                        )
                    )
                )
            )

            # Extract audio data from response
            if response.candidates and response.candidates[0].content.parts:
                data = response.candidates[0].content.parts[0].inline_data.data
            else:
                log(f"No valid response from Gemini API", level="ERROR")
                return None
            return data
        except Exception as e:
            log(f"Error generating multi-speaker audio: {e}", level="ERROR")
            return None

    def _generate_multi_speaker_audio(self, segments):
        """Generate audio using multi-speaker mode, handling more than 2 speakers."""
        # Group segments by speaker pairs
        groups = self._group_segments_by_speaker_pairs(segments)

        if len(groups) == 1:
            # Simple case: 2 or fewer speakers total
            log(f"Generating multi-speaker audio with {len(groups[0]['speakers'])} speakers")
            return self._generate_multi_speaker_audio_for_group(
                groups[0]["segments"],
                groups[0]["speakers"]
            )
        else:
            # Complex case: more than 2 speakers, need to generate multiple audio files
            log(f"Multiple speakers detected. Generating {len(groups)} audio segments with 2-speaker groups")
            audio_segments = []

            for i, group in enumerate(groups):
                log(f"Generating audio for group {i+1}/{len(groups)} with speakers: {list(group['speakers'].keys())}")
                audio_data = self._generate_multi_speaker_audio_for_group(
                    group["segments"],
                    group["speakers"]
                )
                if audio_data:
                    audio_segments.append(audio_data)
                else:
                    log(f"Failed to generate audio for group {i+1}", level="ERROR")

            if not audio_segments:
                return None

            # If we have multiple segments, we need to concatenate them
            # For now, return them as a list that will be handled by the caller
            return audio_segments

    def generate_speech(self, request):
        """
        Generate speech using Google Gemini TTS API.

        Args:
            request: Dictionary containing the TTS request details

        Returns:
            Path to the generated audio file or None if failed
        """
        output_file = request.get("output_file", "")

        if not output_file:
            log("Missing output file path for TTS request", level="ERROR")
            return None

        # Single-speaker mode: process just the text
        text = request.get("text", "")
        voice_id = request.get("voice_id", "Charon")

        if not text:
            log("Missing text for TTS request", level="ERROR")
            return None

        log(f"Generating single-speaker audio for text: {text[:50]}...")
        audio_data = self._generate_single_speaker_audio(text, voice_id)

        if audio_data:
            # Check if we got a list of audio segments (multi-speaker with >2 speakers)
            if isinstance(audio_data, list):
                # Save each audio segment
                segment_files = []
                temp_dir = output_file.replace('.mp3', '_temp')
                os.makedirs(temp_dir, exist_ok=True)

                for i, segment_data in enumerate(audio_data):
                    segment_path = os.path.join(temp_dir, f"group_{i:04d}.wav")
                    self._save_wave_file(segment_path, segment_data)
                    segment_files.append(segment_path)

                # Concatenate all segments
                if self._concatenate_audio_files(segment_files, output_file):
                    # Clean up temp files
                    import shutil
                    shutil.rmtree(temp_dir)
                    return output_file
                else:
                    return None
            else:
                # Single audio data
                # Save the audio file
                output_path = output_file.replace('.mp3', '.wav')  # Gemini outputs WAV format
                self._save_wave_file(output_path, audio_data)
                log(f"Saved audio to {output_path}")

                # Convert to MP3 if needed
                if output_file.endswith('.mp3'):
                    try:
                        import subprocess
                        subprocess.run(['ffmpeg', '-i', output_path, '-acodec', 'mp3', output_file, '-y'],
                                     capture_output=True, check=True)
                        os.remove(output_path)
                        log(f"Converted to MP3: {output_file}")
                        return output_file
                    except Exception as e:
                        log(f"Could not convert to MP3, keeping as WAV: {e}", level="WARNING")
                        return output_path
                else:
                    return output_path

        return None

    def generate_audio_from_request(self, tts_request, output_audio_path):
        """
        Generate audio from a TTS request file.

        Args:
            tts_request: Dictionary containing the TTS request
            output_audio_path: Path where the final audio should be saved

        Returns:
            bool: True if successful, False otherwise
        """
        # Check if TTS file contains groups for multi-speaker mode
        groups = tts_request.get("groups", [])
        if groups:
            log(f"Using pre-grouped segments: {len(groups)} groups")

            # Create a mapping from segment to group
            segment_to_group = {}
            for group_idx, group in enumerate(groups):
                for segment in group.get("segments", []):
                    # Find matching segment in main list by comparing text and character
                    for i, main_segment in enumerate(tts_request.get("segments", [])):
                        if (segment.get("text") == main_segment.get("text") and
                            segment.get("character", "Narrator") == main_segment.get("character", "Narrator")):
                            segment_to_group[i] = group_idx
                            break

                        # Process segments in original order
            # Create chapter directory for temp files
            chapter_dir = os.path.splitext(output_audio_path)[0]  # Remove .mp3 extension
            os.makedirs(chapter_dir, exist_ok=True)
            log(f"Saving audio segments to: {chapter_dir}")

            segment_files = []
            processed_groups = set()
            audio_idx = 0

            segments = tts_request.get("segments", [])
            log(f"Processing {len(segments)} segments in order")

            for i, segment in enumerate(segments):
                if i in segment_to_group:
                    # This segment is part of a group
                    group_idx = segment_to_group[i]

                    # Only process each group once (when we hit its first segment)
                    if group_idx not in processed_groups:
                        processed_groups.add(group_idx)
                        group = groups[group_idx]

                        log(f"Generating audio for group {group_idx+1} with speakers: {list(group['speakers'].keys())}")

                        # Check if we have 1 or 2 speakers
                        if len(group['speakers']) == 1:
                            # Single speaker - concatenate all text and use single-speaker mode
                            speaker_name = list(group['speakers'].keys())[0]
                            voice_id = group['speakers'][speaker_name]
                            combined_text = " ".join([seg.get("text", "") for seg in group["segments"]])
                            log(f"Using single-speaker mode for {speaker_name} (voice: {voice_id})")
                            audio_data = self._generate_single_speaker_audio(combined_text, voice_id)
                        else:
                            # Multi-speaker mode
                            log("Using multi-speaker mode")
                            audio_data = self._generate_multi_speaker_audio_for_group(
                                group["segments"],
                                group["speakers"]
                            )

                        if audio_data:
                            # Save immediately
                            segment_path = os.path.join(chapter_dir, f"segment_{audio_idx:04d}.wav")
                            self._save_wave_file(segment_path, audio_data)
                            segment_files.append(segment_path)
                            log(f"Saved segment {audio_idx+1} to {segment_path}")
                            audio_idx += 1
                        else:
                            log(f"Failed to generate audio for group {group_idx+1}", level="ERROR")
                else:
                    # This segment is not part of any group
                    if segment.get("type") == "dialogue":
                        text = segment.get("text", "")
                        voice_id = segment.get("voice_id", "Charon")
                        character = segment.get("character", "Unknown")
                        log(f"Generating audio for ungrouped dialogue: {character}")
                    else:
                        # Narration
                        text = segment.get("text", "")
                        voice_id = segment.get("voice_id", "Charon")  # Default narrator voice
                        log("Generating audio for ungrouped narration")

                    if text:
                        audio_data = self._generate_single_speaker_audio(text, voice_id)
                        if audio_data:
                            # Save immediately
                            segment_path = os.path.join(chapter_dir, f"segment_{audio_idx:04d}.wav")
                            self._save_wave_file(segment_path, audio_data)
                            segment_files.append(segment_path)
                            log(f"Saved segment {audio_idx+1} to {segment_path}")
                            audio_idx += 1

            # Concatenate all audio segments
            if segment_files:
                log(f"Concatenating {len(segment_files)} audio segments")
                if self._concatenate_audio_files(segment_files, output_audio_path):
                    log(f"Successfully created {output_audio_path}")
                    log(f"Temporary WAV files kept in: {chapter_dir}")
                    return True
                else:
                    return False
            else:
                log("No audio segments generated", level="ERROR")
                return False
        else:
            # Single-speaker mode: process all segments individually
            request = {
                "segments": tts_request.get("segments", []),
                "output_file": output_audio_path
            }
            result = self.generate_speech(request)
            return result is not None



    def _concatenate_audio_files(self, audio_files, output_path):
        """Concatenate multiple audio files into one."""
        try:
            import subprocess

            # Create a file list for ffmpeg
            list_file = output_path.replace('.mp3', '_list.txt')
            with open(list_file, 'w') as f:
                for audio_file in audio_files:
                    # Convert to absolute path for ffmpeg
                    abs_path = os.path.abspath(audio_file)
                    f.write(f"file '{abs_path}'\n")

            # Use ffmpeg to concatenate
            if output_path.endswith('.mp3'):
                # For MP3 output, we need to re-encode
                cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, '-acodec', 'mp3', output_path, '-y']
            else:
                # For WAV output, we can copy directly
                cmd = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', output_path, '-y']

            result = subprocess.run(cmd, capture_output=True, check=True)

            # Clean up list file
            os.remove(list_file)

            log(f"Successfully concatenated {len(audio_files)} audio files to {output_path}")
            return True
        except subprocess.CalledProcessError as e:
            log(f"Error concatenating audio files: {e}", level="ERROR")
            log(f"FFmpeg stderr: {e.stderr.decode('utf-8')}", level="ERROR")
            return False
        except Exception as e:
            log(f"Error concatenating audio files: {e}", level="ERROR")
            return False

    async def generate_audio_from_request_async(self, tts_request, output_audio_path):
        """
        Async version of generate_audio_from_request.

        For Google Gemini, we'll implement true async support if the SDK supports it,
        otherwise we'll run the sync version in a thread pool.
        """
        # Run the synchronous version in a thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_audio_from_request,
            tts_request,
            output_audio_path
        )
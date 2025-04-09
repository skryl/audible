"""
Audio processing module for handling audio files.
"""

import os
from pydub import AudioSegment
from audible.utils.common import log

def stitch_audio_files(chapter_audio_dir, chapter_num, audio_dir, force=False):
    """Stitch together individual audio files into a complete chapter."""
    log(f"Stitching audio files for Chapter {chapter_num}")

    # Define the output file
    output_file = os.path.join(audio_dir, f"chapter_{chapter_num}.mp3")

    # Skip if file exists and not forcing
    if os.path.exists(output_file) and not force:
        log(f"Stitched audio for Chapter {chapter_num} already exists. Use --force to regenerate.")
        return output_file

    # Check if chapter audio directory exists
    if not os.path.exists(chapter_audio_dir):
        log(f"Chapter audio directory not found: {chapter_audio_dir}", level="ERROR")
        return None

    try:
        # Get all audio files in the directory
        audio_files = []
        for file in os.listdir(chapter_audio_dir):
            if file.endswith((".mp3", ".wav")):
                # Extract line number from filename
                file_parts = file.split("_line_")
                if len(file_parts) == 2:
                    line_num = int(file_parts[1].split(".")[0])
                    audio_files.append((line_num, os.path.join(chapter_audio_dir, file)))

        # Sort by line number
        audio_files.sort()

        if not audio_files:
            log(f"No audio files found in {chapter_audio_dir}", level="ERROR")
            return None

        log(f"Found {len(audio_files)} audio files to stitch")

        # Stitch audio files
        combined = AudioSegment.empty()
        for line_num, file_path in audio_files:
            audio = AudioSegment.from_file(file_path)
            combined += audio

            # Add a small pause between lines for natural spacing
            pause = AudioSegment.silent(duration=300)  # 300ms pause
            combined += pause

        # Export to MP3
        combined.export(output_file, format="mp3")
        log(f"Stitched audio saved to {output_file}")

        return output_file

    except Exception as e:
        log(f"Error stitching audio: {e}", level="ERROR")
        return None
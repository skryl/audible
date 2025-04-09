"""
Module for downloading voice samples from YouTube for voice cloning.
"""

import os
import json
import argparse
import subprocess
import shutil
from audible.utils.common import log

def check_dependencies():
    """Check if required dependencies are installed."""
    dependencies = {
        "yt-dlp": False,
        "ffmpeg": False
    }

    # Check for yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        dependencies["yt-dlp"] = True
    except (subprocess.SubprocessError, FileNotFoundError):
        log("yt-dlp is not installed", level="WARNING")

    # Check for ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        dependencies["ffmpeg"] = True
    except (subprocess.SubprocessError, FileNotFoundError):
        log("ffmpeg is not installed", level="WARNING")

    # Install missing dependencies
    missing = [dep for dep, installed in dependencies.items() if not installed]

    if missing:
        log(f"Missing dependencies: {', '.join(missing)}. Installing now...", level="WARNING")

        for dep in missing:
            try:
                if dep == "yt-dlp":
                    subprocess.run(["pip", "install", "yt-dlp"], check=True)
                    log("yt-dlp installed successfully")
                    dependencies["yt-dlp"] = True
                elif dep == "ffmpeg":
                    log("ffmpeg must be installed manually. On macOS: brew install ffmpeg", level="ERROR")
                    log("On Ubuntu/Debian: sudo apt install ffmpeg", level="ERROR")
                    log("See https://ffmpeg.org/download.html for other platforms", level="ERROR")
            except subprocess.SubprocessError:
                log(f"Failed to install {dep}", level="ERROR")

    return all(dependencies.values())

def download_audio(youtube_url, output_file, audio_format="mp3"):
    """Download audio from a YouTube URL using yt-dlp."""
    log(f"Downloading audio from: {youtube_url}")

    # Fix potential URL escaping issues by unescaping any backslashes
    # Replace any backslash-escaped characters like \? or \= with their unescaped versions
    clean_url = youtube_url.replace('\\', '')
    log(f"Using cleaned URL: {clean_url}")

    # Create base command
    command = [
        "yt-dlp",
        "-x",  # Extract audio
        "--audio-format", audio_format,  # Set audio format
        "--audio-quality", "0",  # Best quality
        "-o", output_file,  # Output file
    ]

    # Add the cleaned URL
    command.append(clean_url)

    try:
        # Run the command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        log("Audio downloaded successfully")
        return True, None
    except subprocess.CalledProcessError as e:
        log(f"Error downloading audio: {e}", level="ERROR")
        log(f"Error details: {e.stderr}", level="ERROR")
        return False, e.stderr

def trim_audio_with_ffmpeg(input_file, output_file, start_time=None, end_time=None):
    """Trim audio file using ffmpeg."""
    log(f"Trimming audio file with ffmpeg: {input_file}")

    # Create base command
    command = ["ffmpeg", "-y", "-i", input_file]

    # Add trim parameters if specified
    if start_time is not None:
        # Convert seconds to HH:MM:SS format for ffmpeg
        start_str = str(start_time)
        if isinstance(start_time, int) or isinstance(start_time, float):
            hours, remainder = divmod(int(start_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            start_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        command.extend(["-ss", start_str])

    if end_time is not None and start_time is not None:
        # Calculate duration instead of end time
        duration = end_time - start_time
        hours, remainder = divmod(int(duration), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        command.extend(["-t", duration_str])
    elif end_time is not None:
        # If only end time is specified (no start time)
        end_str = str(end_time)
        if isinstance(end_time, int) or isinstance(end_time, float):
            hours, remainder = divmod(int(end_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            end_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        command.extend(["-to", end_str])

    # Add output format options and output file
    command.extend(["-acodec", "copy", output_file])

    try:
        # Run the command
        log(f"Running ffmpeg command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        log("Audio trimmed successfully")
        return True, None
    except subprocess.CalledProcessError as e:
        log(f"Error trimming audio: {e}", level="ERROR")
        log(f"Error details: {e.stderr}", level="ERROR")
        return False, e.stderr

def get_audio_duration(audio_file):
    """Get duration of audio file in seconds using ffmpeg."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except (subprocess.SubprocessError, ValueError) as e:
        log(f"Error getting audio duration: {e}", level="ERROR")
        return None

def setup_voice_clone_dir(book_dir):
    """Set up voice_clone directory for the book."""
    voice_clone_dir = os.path.join(book_dir, "voice_clone")

    if not os.path.exists(voice_clone_dir):
        os.makedirs(voice_clone_dir)
        log(f"Created voice_clone directory at {voice_clone_dir}")

    return voice_clone_dir

def normalize_character_name(name):
    """Normalize character name for filename."""
    # Remove special characters and spaces
    safe_name = name.replace(' ', '_').replace("'", "").replace('"', "")
    return safe_name.lower()

def parse_time(time_str):
    """Parse time string in format MM:SS or HH:MM:SS to seconds."""
    if not time_str:
        return None

    parts = time_str.split(':')
    if len(parts) == 2:  # MM:SS
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:  # HH:MM:SS
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use MM:SS or HH:MM:SS")

def check_existing_character(voice_mappings_path, character_name, match_case=False):
    """Check if character exists in voice_mappings.json and get its exact name."""
    if not os.path.exists(voice_mappings_path):
        return None

    try:
        with open(voice_mappings_path, 'r', encoding='utf-8') as f:
            voice_mappings = json.load(f)
    except Exception as e:
        log(f"Error reading voice mappings file: {e}", level="WARNING")
        return None

    # Check for exact match first
    if character_name in voice_mappings:
        return character_name

    # If not match_case, check for case-insensitive match
    if not match_case:
        for name in voice_mappings.keys():
            if name.lower() == character_name.lower():
                return name

    return None

def download_voice_sample(youtube_url, character_name, book_dir, start_time=None, end_time=None,
                         audio_format="mp3", match_case=False):
    """
    Download an audio sample from YouTube for use in voice cloning.

    Args:
        youtube_url (str): URL of the YouTube video.
        character_name (str): Name of the character for voice cloning.
        book_dir (str): Directory containing the book data.
        start_time (str, optional): Start time for audio clip (MM:SS or HH:MM:SS).
        end_time (str, optional): End time for audio clip (MM:SS or HH:MM:SS).
        audio_format (str, optional): Format for the output audio file (mp3, wav, m4a).
        match_case (bool, optional): Whether to match character name case in voice_mappings.json.

    Returns:
        bool: True if successful, False otherwise.
    """
    # Check dependencies
    if not check_dependencies():
        log("Required dependencies are missing. Please install them and try again.", level="ERROR")
        return False

    # Convert time strings to seconds if provided
    start_seconds = parse_time(start_time) if start_time else None
    end_seconds = parse_time(end_time) if end_time else None

    # Set up voice_clone directory
    voice_clone_dir = setup_voice_clone_dir(book_dir)

    # Check for voice_mappings.json in the tts directory first
    tts_dir = os.path.join(book_dir, "tts")
    voice_mappings_path = os.path.join(tts_dir, "voice_mappings.json")

    # Check if character exists in voice_mappings.json
    existing_character = check_existing_character(voice_mappings_path, character_name, match_case)

    # Use existing character name if found, otherwise use the provided name
    if existing_character:
        log(f"Found existing character '{existing_character}' in voice mappings")
        character_name = existing_character
    else:
        log(f"Character '{character_name}' not found in voice mappings. Will use this name.")

    # Normalize character name for the filename
    normalized_name = normalize_character_name(character_name)
    temp_audio_file = os.path.join(voice_clone_dir, f"{normalized_name}_temp.{audio_format}")
    final_audio_file = os.path.join(voice_clone_dir, f"{normalized_name}.{audio_format}")

    # Download audio from YouTube
    download_success, error = download_audio(youtube_url, temp_audio_file, audio_format)
    if not download_success:
        log(f"Failed to download audio: {error}", level="ERROR")
        return False

    # If trimming is needed
    if start_seconds is not None or end_seconds is not None:
        # Get audio duration if end_time not specified
        if end_seconds is None:
            duration = get_audio_duration(temp_audio_file)
            if duration:
                end_seconds = duration
                log(f"Audio duration: {duration:.2f} seconds")
            else:
                log("Could not determine audio duration. Will not trim end.", level="WARNING")

        # Trim audio
        trim_success, error = trim_audio_with_ffmpeg(temp_audio_file, final_audio_file, start_seconds, end_seconds)
        if not trim_success:
            log(f"Failed to trim audio: {error}", level="ERROR")
            # Still try to use the original file
            shutil.copy2(temp_audio_file, final_audio_file)
            log("Using untrimmed audio file instead", level="WARNING")
    else:
        # Use the downloaded file directly
        os.rename(temp_audio_file, final_audio_file)

    # Clean up temporary files
    if os.path.exists(temp_audio_file):
        os.remove(temp_audio_file)

    log(f"Voice sample for '{character_name}' downloaded and saved to {final_audio_file}")
    log("Ready for voice cloning. Use the clone_voices tool to create a cloned voice.")
    return True

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Download audio from YouTube for voice cloning')
    parser.add_argument('--url', type=str, required=True,
                        help='YouTube URL to download audio from')
    parser.add_argument('--character', type=str, required=True,
                        help='Character name for the voice sample')
    parser.add_argument('--book_dir', type=str, default='.',
                        help='Directory containing the book data')
    parser.add_argument('--start', type=str, default=None,
                        help='Start time for audio clip (format: MM:SS or HH:MM:SS)')
    parser.add_argument('--end', type=str, default=None,
                        help='End time for audio clip (format: MM:SS or HH:MM:SS)')
    parser.add_argument('--format', type=str, choices=['mp3', 'wav', 'm4a'], default='mp3',
                        help='Audio format for the output file')
    parser.add_argument('--match_case', action='store_true',
                        help='Match character name case in voice_mappings.json')

    return parser.parse_args()

def main():
    """Command-line entry point for downloading voice samples."""
    args = parse_args()

    download_voice_sample(
        youtube_url=args.url,
        character_name=args.character,
        book_dir=args.book_dir,
        start_time=args.start,
        end_time=args.end,
        audio_format=args.format,
        match_case=args.match_case
    )

if __name__ == "__main__":
    main()
"""
Module for cloning voices using Cartesia API.
"""

import os
import json
import argparse
import time
import shutil
from cartesia import Cartesia
from audible.utils.common import log

def get_cartesia_client():
    """Initialize and return Cartesia client."""
    api_key = os.getenv("CARTESIA_API_KEY")
    if not api_key:
        log("Error: CARTESIA_API_KEY not found in environment variables", level="ERROR")
        return None
    return Cartesia(api_key=api_key)

def get_character_names(voice_clone_dir):
    """Get list of character names based on audio files in voice_clone directory."""
    if not os.path.exists(voice_clone_dir):
        log(f"Creating voice_clone directory at {voice_clone_dir}")
        os.makedirs(voice_clone_dir)
        return []

    character_names = []
    valid_extensions = ['.mp3', '.wav', '.m4a', '.ogg']

    for filename in os.listdir(voice_clone_dir):
        name, ext = os.path.splitext(filename)
        if ext.lower() in valid_extensions and not name.endswith('_cloned'):
            character_names.append(name)

    return character_names

def create_cloned_voice(client, character_name, audio_file_path, wait_for_completion=True):
    """Clone a voice using Cartesia API and return the cloned voice ID."""
    log(f"Cloning voice for character: {character_name}")

    try:
        log(f"Submitting voice cloning job for {character_name}")
        voice_name = f"{character_name} (Cloned)"

        # Initiate voice cloning job
        with open(audio_file_path, 'rb') as audio_file:
            response = client.voices.clone(
                clip=audio_file,  # The API expects 'clip' parameter
                name=voice_name,
                description=f"Cloned voice for character {character_name}",
                language="en",    # Using English for all clones
                mode="stability", # 'stability' is better for longer samples
                enhance=True      # Enhance audio quality
            )

        # Get the voice ID from the response
        voice_id = response.id
        log(f"Voice cloning job submitted for {character_name}, job ID: {voice_id}")

        # Skip waiting for completion if requested
        if not wait_for_completion:
            log(f"Skipping wait for completion. Voice ID: {voice_id} (status: processing)")
            return voice_id

        # Wait for the voice cloning job to complete
        # The VoiceMetadata object doesn't have a status property directly
        # So we need to get the voice status by querying it
        max_attempts = 60  # Maximum number of status check attempts
        attempt = 0

        # Wait a moment before first status check
        time.sleep(5)

        # Get the initial status
        try:
            voice = client.voices.get(voice_id)
            status = getattr(voice, 'status', None)
            log(f"Initial voice cloning status: {status}")
        except Exception as e:
            log(f"Error checking initial voice status: {e}", level="WARNING")
            status = None

        while status not in ["ready", "failed"] and attempt < max_attempts:
            attempt += 1
            time.sleep(10)  # Wait for 10 seconds before checking again

            # Get the latest status
            try:
                voice = client.voices.get(voice_id)
                status = getattr(voice, 'status', None)
                log(f"Voice cloning status for {character_name}: {status} (attempt {attempt}/{max_attempts})")
            except Exception as e:
                log(f"Error checking voice status: {e}", level="WARNING")
                # Continue trying even if one status check fails

        if status == "ready":
            log(f"Voice cloning successful for {character_name}. Voice ID: {voice_id}")
            return voice_id
        else:
            log(f"Voice cloning status is '{status}' after timeout. Using voice ID anyway: {voice_id}", level="WARNING")
            return voice_id  # Return the ID anyway, as the job might complete later

    except Exception as e:
        log(f"Error cloning voice for {character_name}: {e}", level="ERROR")
        return None

def load_voice_mappings(voice_mappings_path):
    """Load existing voice mappings JSON file."""
    if os.path.exists(voice_mappings_path):
        try:
            with open(voice_mappings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading voice mappings: {e}", level="ERROR")
            return {}
    else:
        log(f"Voice mappings file not found. Will create new file.", level="WARNING")
        return {}

def update_voice_mappings(voice_mappings, character_name, cloned_voice_id):
    """Update voice mappings with the new cloned voice ID."""
    # Check for existing character with different case
    existing_character = None
    for name in voice_mappings.keys():
        if name.lower() == character_name.lower():
            existing_character = name
            break

    # Use existing character name if found, otherwise use the provided name
    key_to_use = existing_character if existing_character else character_name

    if key_to_use not in voice_mappings:
        voice_mappings[key_to_use] = {}

    # Add or update the Cartesia voice ID with the cloned voice
    voice_mappings[key_to_use]["cartesia"] = cloned_voice_id

    return voice_mappings

def save_voice_mappings(voice_mappings, voice_mappings_path, backup=True):
    """Save updated voice mappings to file, with optional backup of the original."""
    # Create backup if requested
    if backup and os.path.exists(voice_mappings_path):
        backup_path = f"{voice_mappings_path}.bak.{int(time.time())}"
        shutil.copy2(voice_mappings_path, backup_path)
        log(f"Created backup of voice mappings at {backup_path}")

    # Save updated mappings
    try:
        with open(voice_mappings_path, 'w', encoding='utf-8') as f:
            json.dump(voice_mappings, f, indent=2)
        log(f"Saved updated voice mappings to {voice_mappings_path}")
        return True
    except Exception as e:
        log(f"Error saving voice mappings: {e}", level="ERROR")
        return False

def clone_voices(book_dir, character=None, voice_clone_dir=None, wait_for_completion=True, create_backup=True):
    """Clone voices for characters using Cartesia API and update voice mappings."""
    log("Starting voice cloning process")

    # Determine voice clone directory
    voice_clone_dir = voice_clone_dir if voice_clone_dir else os.path.join(book_dir, "voice_clone")

    # Check for voice_mappings.json in the tts directory first
    voices_dir = os.path.join(book_dir, "voices")
    voice_mappings_path = os.path.join(voices_dir, "voice_mappings.json")

    log(f"Using book directory: {book_dir}")
    log(f"Using voice clone directory: {voice_clone_dir}")
    log(f"Using voice mappings path: {voice_mappings_path}")

    # Get Cartesia client
    client = get_cartesia_client()
    if not client:
        log("Failed to initialize Cartesia client. Exiting.", level="ERROR")
        return False

    # Get character names from voice samples
    all_characters = get_character_names(voice_clone_dir)

    if not all_characters:
        log(f"No voice samples found in {voice_clone_dir}. Please add audio files named after characters.", level="WARNING")
        return False

    log(f"Found {len(all_characters)} character voice samples: {', '.join(all_characters)}")

    # Filter characters if specific character requested
    characters_to_process = [c for c in all_characters if not character or c.lower() == character.lower()]

    if character and not characters_to_process:
        log(f"Character '{character}' not found in voice samples.", level="ERROR")
        return False

    # Load existing voice mappings
    voice_mappings = load_voice_mappings(voice_mappings_path)

    # Track if we need to save voice mappings at the end
    mappings_updated = False

    # Process each character
    for character_name in characters_to_process:
        # Get audio file path
        for ext in ['.mp3', '.wav', '.m4a', '.ogg']:
            audio_file = os.path.join(voice_clone_dir, f"{character_name}{ext}")
            if os.path.exists(audio_file):
                break
        else:
            log(f"Could not find audio file for {character_name}", level="ERROR")
            continue

        # Create cloned voice
        cloned_voice_id = create_cloned_voice(client, character_name, audio_file, wait_for_completion)

        if cloned_voice_id:
            # Update voice mappings
            voice_mappings = update_voice_mappings(voice_mappings, character_name, cloned_voice_id)
            mappings_updated = True

            # Save voice mappings after each successful cloning
            # This ensures we don't lose progress if the script is interrupted
            if save_voice_mappings(voice_mappings, voice_mappings_path, backup=create_backup and not mappings_updated):
                log(f"Saved voice mapping for {character_name}")
                # Only create backup for the first save
                create_backup = False

            # Create a copy of the cloned audio for reference
            cloned_audio_file = os.path.join(voice_clone_dir, f"{character_name}_cloned{os.path.splitext(audio_file)[1]}")
            shutil.copy2(audio_file, cloned_audio_file)
            log(f"Saved a copy of the cloned audio as {cloned_audio_file}")

    log("Voice cloning process completed successfully")
    return True

def parse_args():
    """Parse command line arguments for voice cloning."""
    parser = argparse.ArgumentParser(description='Clone voices using Cartesia API and update voice mappings')
    parser.add_argument('--book_dir', type=str, required=True,
                        help='Directory containing the book data')
    parser.add_argument('--voice_clone_dir', type=str, default=None,
                        help='Directory containing voice samples to clone (defaults to {book_dir}/voice_clone)')
    parser.add_argument('--character', type=str, default=None,
                        help='Only clone voice for a specific character')
    parser.add_argument('--no_wait', action='store_true',
                        help='Do not wait for voice cloning jobs to complete (faster)')
    parser.add_argument('--no_backup', action='store_true',
                        help='Do not create a backup of the original voice_mappings.json')

    return parser.parse_args()

def main():
    """Command-line entry point for voice cloning."""
    args = parse_args()
    clone_voices(
        book_dir=args.book_dir,
        character=args.character,
        voice_clone_dir=args.voice_clone_dir,
        wait_for_completion=not args.no_wait,
        create_backup=not args.no_backup
    )

if __name__ == "__main__":
    main()
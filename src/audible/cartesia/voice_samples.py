"""
Module for generating voice samples using OpenAI and Cartesia APIs.
"""

import os
import json
import argparse
from openai import OpenAI
from cartesia import Cartesia
from audible.utils.common import log

def load_voice_mappings(book_dir):
    """Load voice mappings from the specified directory."""
    # Check for voice_mappings.json in the tts directory first
    tts_dir = os.path.join(book_dir, "tts")
    voices_file_path = os.path.join(tts_dir, "voice_mappings.json")

    if not os.path.exists(voices_file_path):
        log(f"Error: Voice mappings file not found in tts directory or book root", level="ERROR")
        return None

    try:
        with open(voices_file_path, 'r', encoding='utf-8') as f:
            voice_mapping = json.load(f)
        log(f"Loaded voice mapping for {len(voice_mapping)} characters from {voices_file_path}")
        return voice_mapping
    except Exception as e:
        log(f"Error loading voice mappings: {e}", level="ERROR")
        return None

def generate_openai_sample(character_name, voice_id, output_dir, sample_text=None):
    """Generate a voice sample using OpenAI's TTS API."""
    log(f"Generating OpenAI sample for {character_name} with voice {voice_id}")

    if not sample_text:
        sample_text = f"Hello, I am {character_name}. This is a sample of my voice using OpenAI's text-to-speech service."

    # Create a safe filename
    safe_name = character_name.replace(' ', '_').replace("'", "").replace('"', "").lower()
    output_file = os.path.join(output_dir, f"{safe_name}_openai.mp3")

    # Skip if file already exists
    if os.path.exists(output_file):
        log(f"Sample already exists at {output_file}. Skipping.")
        return output_file

    try:
        client = OpenAI()
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice_id,
            input=sample_text
        )

        # Save the audio file
        response.stream_to_file(output_file)
        log(f"Saved OpenAI sample to {output_file}")
        return output_file
    except Exception as e:
        log(f"Error generating OpenAI sample: {e}", level="ERROR")
        return None

def generate_cartesia_sample(character_name, voice_id, output_dir, sample_text=None):
    """Generate a voice sample using Cartesia's TTS API."""
    log(f"Generating Cartesia sample for {character_name} with voice {voice_id}")

    if not sample_text:
        sample_text = f"Hello, I am {character_name}. This is a sample of my voice using Cartesia's text-to-speech service."

    # Create a safe filename
    safe_name = character_name.replace(' ', '_').replace("'", "").replace('"', "").lower()
    output_file = os.path.join(output_dir, f"{safe_name}_cartesia.wav")

    # Skip if file already exists
    if os.path.exists(output_file):
        log(f"Sample already exists at {output_file}. Skipping.")
        return output_file

    try:
        client = Cartesia(api_key=os.getenv("CARTESIA_API_KEY"))

        # The response is a generator, so we need to consume it
        audio_data = bytes()

        for chunk in client.tts.bytes(
            model_id="sonic-2",
            transcript=sample_text,
            voice={"id": voice_id},
            language="en",
            output_format={
                "container": "wav",
                "sample_rate": 44100,
                "encoding": "pcm_s16le"
            },
        ):
            audio_data += chunk

        # Save the audio file
        with open(output_file, 'wb') as f:
            f.write(audio_data)

        log(f"Saved Cartesia sample to {output_file}")
        return output_file
    except Exception as e:
        log(f"Error generating Cartesia sample: {e}", level="ERROR")
        return None

def generate_voice_samples(book_dir, output_dir=None, use_openai=True, use_cartesia=True,
                          sample_text=None, force=False, character=None):
    """Generate voice samples for all characters in voice mappings."""
    log("Starting voice sample generation")

    # Determine output directory
    output_dir = output_dir if output_dir else os.path.join(book_dir, "voice_samples")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        log(f"Created output directory at {output_dir}")

    # Load voice mappings
    voice_mapping = load_voice_mappings(book_dir)
    if not voice_mapping:
        log("Failed to load voice mappings. Exiting.", level="ERROR")
        return False

    # Generate samples for each character
    for character_name, voices in voice_mapping.items():
        # Skip if not the specified character
        if character and character.lower() != character_name.lower():
            continue

        log(f"Processing samples for {character_name}")

        # Generate OpenAI sample if requested
        if use_openai and "openai" in voices:
            openai_voice_id = voices["openai"]
            output_file = os.path.join(output_dir, f"{character_name.replace(' ', '_').lower()}_openai.mp3")

            # Check if we need to regenerate
            if force and os.path.exists(output_file):
                log(f"Force mode: Removing existing OpenAI sample {output_file}")
                os.remove(output_file)

            generate_openai_sample(character_name, openai_voice_id, output_dir, sample_text)

        # Generate Cartesia sample if requested
        if use_cartesia and "cartesia" in voices:
            cartesia_voice_id = voices["cartesia"]
            output_file = os.path.join(output_dir, f"{character_name.replace(' ', '_').lower()}_cartesia.wav")

            # Check if we need to regenerate
            if force and os.path.exists(output_file):
                log(f"Force mode: Removing existing Cartesia sample {output_file}")
                os.remove(output_file)

            generate_cartesia_sample(character_name, cartesia_voice_id, output_dir, sample_text)

    log("Voice sample generation complete!")
    return True

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Generate voice samples for all voices in voice_mappings.json')
    parser.add_argument('--book_dir', type=str, default='.',
                        help='Directory containing the voice_mappings.json file')
    parser.add_argument('--output_dir', type=str, default=None,
                        help='Directory to save voice samples (defaults to {book_dir}/voice_samples)')
    parser.add_argument('--openai', action='store_true',
                        help='Generate only OpenAI voice samples')
    parser.add_argument('--cartesia', action='store_true',
                        help='Generate only Cartesia voice samples')
    parser.add_argument('--sample_text', type=str, default=None,
                        help='Custom sample text to use instead of default')
    parser.add_argument('--force', action='store_true',
                        help='Force regeneration of existing samples')
    parser.add_argument('--character', type=str, default=None,
                        help='Generate sample for a specific character only')

    return parser.parse_args()

def main():
    """Command-line entry point for voice sample generation."""
    args = parse_args()

    use_openai = not args.cartesia or args.openai
    use_cartesia = not args.openai or args.cartesia

    generate_voice_samples(
        book_dir=args.book_dir,
        output_dir=args.output_dir,
        use_openai=use_openai,
        use_cartesia=use_cartesia,
        sample_text=args.sample_text,
        force=args.force,
        character=args.character
    )

if __name__ == "__main__":
    main()
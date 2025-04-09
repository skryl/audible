"""
TTS preparation for Audible.

This module provides functionality for preparing TTS request files from scripts.
"""

import os
import json
import copy
from audible.utils.common import (
    log, extract_chapter_num, get_padded_chapter_num, get_chapter_filename,
    get_best_string_match
)

def prepare_tts(book_dir, force=False, provider=None):
    """
    Prepare TTS request files from scripts.

    Args:
        book_dir (str): Directory containing the book data
        force (bool): Force regeneration of TTS files even if they exist
        provider (str, optional): TTS provider name (e.g., 'openai', 'cartesia')

    Returns:
        bool: True if successful, False otherwise
    """
    # Get provider from environment variable if not specified
    if provider is None:
        provider = os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()
        
    log(f"Preparing TTS requests for book in {book_dir} using {provider} provider")

    # Create tts directory if it doesn't exist
    tts_dir = os.path.join(book_dir, "tts")
    voices_dir = os.path.join(book_dir, "voices")

    if not os.path.exists(tts_dir):
        os.makedirs(tts_dir)
        log(f"Created TTS directory at {tts_dir}")

    # Characters directory path
    characters_dir = os.path.join(book_dir, "characters")

    # Check for character information in characters directory
    characters_file = os.path.join(characters_dir, "characters.json")

    with open(characters_file, "r", encoding="utf-8") as f:
        characters = json.load(f)

    # Check for voice mappings in the tts directory first
    voice_mappings_file = os.path.join(voices_dir, "voice_mappings.json")

    voice_mappings = {}
    if os.path.exists(voice_mappings_file):
        with open(voice_mappings_file, "r", encoding="utf-8") as f:
            voice_mappings = json.load(f)
        log(f"Loaded voice mappings from {voice_mappings_file}")

        # Validate voice mappings for the current provider
        validate_voice_mappings(voice_mappings, list(characters.keys()))
    else:
        log("No voice mappings file found. Will use default voices.")

    # Check for scripts
    scripts_dir = os.path.join(book_dir, "scripts")
    if not os.path.exists(scripts_dir):
        log(f"Scripts directory not found at {scripts_dir}. Run generate_scripts first.", level="ERROR")
        return False

    # Get all script files
    script_files = sorted([f for f in os.listdir(scripts_dir) if f.endswith("_script.json")])
    if not script_files:
        log(f"No script files found in {scripts_dir}", level="ERROR")
        return False

    log(f"Found {len(script_files)} script files")

    # Calculate padding digits based on total number of script files
    num_chapters = len(script_files)

    # Process each script to create TTS request files
    for script_file in script_files:
        # Extract chapter number from the script filename
        chapter_num_match = script_file.split("_")
        if len(chapter_num_match) >= 2 and "chapter" in script_file:
            try:
                # Try to extract the number from format "chapter_XX_script.json"
                chapter_num = int(chapter_num_match[1])
            except (ValueError, IndexError):
                log(f"Could not extract chapter number from script filename: {script_file}", level="ERROR")
                continue
        else:
            log(f"Unexpected script filename format: {script_file}", level="ERROR")
            continue

        # Get the TTS filename using the utility function
        tts_file = get_chapter_filename(
            book_dir, chapter_num, 'tts', num_chapters=num_chapters, 
        )

        # Skip if TTS file exists and we're not forcing regeneration
        if os.path.exists(tts_file) and not force:
            log(f"TTS request file for chapter {chapter_num} already exists. Use --force to regenerate.")
            continue

        # Load script
        script_path = os.path.join(scripts_dir, script_file)
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)

        log(f"Preparing TTS request for chapter {chapter_num}")

        # Generate the TTS request
        tts_request = generate_tts_request(script, voice_mappings, characters)

        # Save the TTS request to file
        with open(tts_file, "w", encoding="utf-8") as f:
            json.dump(tts_request, f, indent=2)
        log(f"Saved TTS request for chapter {chapter_num}")

    log("TTS preparation complete")
    return True

def generate_tts_request(script, voice_mappings, characters):
    """Generate a TTS request from a script."""
    # Create a copy of the script to convert to TTS request format
    tts_request = copy.deepcopy(script)

    # Debug: Print voice mappings structure for Cartesia provider
    provider = os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()
    if provider == "cartesia":
        log("Voice mappings for Cartesia (DEBUG):", level="DEBUG")
        for char_name, voices in voice_mappings.items():
            if isinstance(voices, dict) and "cartesia" in voices:
                log(f"  {char_name}: {voices['cartesia']}", level="DEBUG")

    # Add metadata to the request
    tts_request["status"] = "pending"  # Will be changed to "processed" once audio is generated
    chapter_num = tts_request.get("chapter_number", 0)
    # Get padded chapter number for audio file name
    padded_chapter_num = get_padded_chapter_num(chapter_num)
    tts_request["audio_file"] = f"chapter_{padded_chapter_num}.mp3"

    # Process segments to add voice IDs
    segments = tts_request.get("segments", [])
    for i, segment in enumerate(segments):
        segment_type = segment.get("type", "narration")

        # Handle different segment types
        if segment_type == "dialogue":
            # Get character name
            character = segment.get("character", "Narrator")

            # Look up voice mapping
            voice_id = get_voice_id(character, voice_mappings)
            if voice_id:
                segment["voice_id"] = voice_id

            # Add emotion markers if not present
            if "emotion" not in segment:
                segment["emotion"] = "neutral"

            # Add voice characteristics from character profile
            character_voice_traits = extract_voice_characteristics(character, characters)
            if character_voice_traits:
                segment["character_voice_traits"] = character_voice_traits

        elif segment_type == "narration":
            # Use narrator voice for narration
            voice_id = get_voice_id("Narrator", voice_mappings)
            if voice_id:
                segment["voice_id"] = voice_id

            # Add voice characteristics for narrator if available
            character_voice_traits = extract_voice_characteristics("Narrator", characters)
            if character_voice_traits:
                segment["character_voice_traits"] = character_voice_traits
            else:
                segment["character_voice_traits"] = """Voice Affect: Low, hushed, and suspenseful narration voice; convey tension and intrigue.\n\n Pronunciation: British accent, slightly elongated vowels and softened consonants for an eerie, haunting effect.\n\n Pauses: Insert meaningful pauses to enhance suspense.
                """

    return tts_request

def extract_voice_characteristics(character_name, characters):
    """
    Extract voice characteristics from character profiles using string similarity matching.

    Args:
        character_name (str): Name of the character
        characters (list or dict): Character profiles, either as a list of dictionaries or a dictionary

    Returns:
        str: Formatted voice characteristics or None if not found
    """
    # Safety check - ensure characters is iterable
    if not characters or not isinstance(characters, (list, dict)):
        log(f"Invalid characters data for {character_name}: {type(characters)}", level="WARNING")
        return None

    # Enable debug output when in DEBUG mode
    enable_debug = os.getenv("AUDIBLE_LOG_LEVEL", "INFO").upper() == "DEBUG"

    # Debug: Show character data structure
    if enable_debug:
        log(f"Looking for voice characteristics for '{character_name}'", level="DEBUG")
        if isinstance(characters, dict):
            log(f"Character dictionary keys: {list(characters.keys())[:5]}... ({len(characters)} total)", level="DEBUG")
        else:
            log(f"Character list length: {len(characters)}", level="DEBUG")

    # First try direct match in dictionary
    if isinstance(characters, dict) and character_name in characters:
        data = characters[character_name]
        if enable_debug:
            log(f"Direct match found for '{character_name}' in characters dictionary", level="DEBUG")

        if isinstance(data, dict) and "voice" in data:
            voice_traits = data["voice"]
            log(f"Using direct match voice traits for '{character_name}'", level="DEBUG")
            if isinstance(voice_traits, dict):
                return ", ".join([f"{k}: {v}" for k, v in voice_traits.items()])
            elif isinstance(voice_traits, str):
                return voice_traits

    # If no direct match, use string matching
    best_match, similarity, data = get_best_string_match(
        character_name,
        characters,
        threshold=0.6,
        debug=enable_debug
    )

    if best_match and data and isinstance(data, dict):
        log(f"Using voice traits for '{best_match}' (similarity: {similarity:.2f}) for character '{character_name}'")

        # Debug voice trait structure
        if enable_debug:
            log(f"Character data keys: {list(data.keys())}", level="DEBUG")
            if "voice" in data:
                log(f"Voice data type: {type(data['voice']).__name__}", level="DEBUG")

        # Get voice traits if available - check both "voice_traits" and "voice" keys
        for trait_key in ["voice_traits", "voice"]:
            if trait_key in data:
                voice_traits = data[trait_key]
                if isinstance(voice_traits, dict):
                    return ", ".join([f"{k}: {v}" for k, v in voice_traits.items()])
                elif isinstance(voice_traits, str):
                    return voice_traits

    log(f"No matching character found for '{character_name}'", level="DEBUG")
    return None

def get_voice_id(character_name, voice_mappings):
    """Get the appropriate voice ID for a character using string similarity matching."""
    provider = os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()

    # Log info for debugging
    log(f"Looking for voice ID for character '{character_name}' with provider '{provider}'", level="DEBUG")

    # Debug voice mappings in DEBUG mode
    log(f"Available voice mappings keys: {list(voice_mappings.keys())}", level="DEBUG")

    # Enable verbose debug output when trying to match character voices
    enable_debug = os.getenv("AUDIBLE_LOG_LEVEL", "INFO").upper() == "DEBUG"

    # Get the best match from voice_mappings with debug info
    best_match, similarity, voices = get_best_string_match(
        character_name,
        voice_mappings,
        threshold=0.8,
        debug=enable_debug
    )

    # First try a direct exact match (case-insensitive) in the voice_mappings
    char_lower = character_name.lower()
    for mapping_name, voices_dict in voice_mappings.items():
        if mapping_name.lower() == char_lower and isinstance(voices_dict, dict) and provider in voices_dict:
            voice_id = voices_dict.get(provider)
            if voice_id:
                log(f"Found exact match for character '{character_name}' with voice ID: {voice_id}", level="DEBUG")
                return voice_id

    # If no exact match, use the similarity match
    if best_match:
        log(f"Best match found: '{best_match}' for character '{character_name}'", level="DEBUG")

        # With our fixed string matching, voices should be the dictionary of provider->voice_id mappings
        log(f"Match data type: {type(voices).__name__}", level="DEBUG")
        if isinstance(voices, dict):
            log(f"Voice providers available: {list(voices.keys())}", level="DEBUG")
        else:
            log(f"Unexpected match data: {voices}", level="DEBUG")

        log(f"Looking for provider '{provider}' in match data", level="DEBUG")

        # Check if we have a valid match with voice data
        if voices and isinstance(voices, dict) and provider in voices:
            voice_id = voices.get(provider)
            if voice_id:
                log(f"Using voice for '{best_match}' (similarity: {similarity:.2f}) for character '{character_name}'")
                return voice_id
            else:
                log(f"Voice ID for provider '{provider}' is empty or None", level="DEBUG")
        else:
            log(f"Provider '{provider}' not found in voice data for best match '{best_match}'", level="DEBUG")

    # Check for default voice - try both uppercase and lowercase versions
    for default_key in ["DEFAULT", "default"]:
        if default_key in voice_mappings and provider in voice_mappings[default_key]:
            log(f"Using {default_key} voice for character '{character_name}' (no good match found)")
            return voice_mappings[default_key].get(provider)

    # If no default for current provider, try "Narrator" as fallback (also check for uppercase version)
    for narrator_key in ["NARRATOR", "Narrator", "narrator"]:
        if narrator_key in voice_mappings and provider in voice_mappings[narrator_key]:
            log(f"Using {narrator_key} voice for character '{character_name}' (no match or default found)")
            return voice_mappings[narrator_key].get(provider)

    # If no mapping found, return None (the TTS provider will use a default voice)
    log(f"No voice mapping or default found for character '{character_name}' with provider '{provider}'. TTS provider will use its default voice.")
    return None

def prepare_voice_mappings(book_dir, force=False):
    """
    Create voice_mappings.json for all characters found in characters.json
    with default voices for OpenAI and Cartesia providers.
    
    Args:
        book_dir (str): Directory containing the book data
        force (bool): Force regeneration of voice mappings even if they exist
    """
    log(f"Preparing voice mappings for book in {book_dir}")
    
    # Ensure voices directory exists
    voices_dir = os.path.join(book_dir, "voices")
    if not os.path.exists(voices_dir):
        os.makedirs(voices_dir)
        log(f"Created voices directory at {voices_dir}")
        
    # Characters directory path
    characters_dir = os.path.join(book_dir, "characters")
    
    # Check for character information in characters directory
    characters_file = os.path.join(characters_dir, "characters.json")
    if not os.path.exists(characters_file):
        log(f"Characters file not found at {characters_file}. Run extract_characters first.", level="ERROR")
        return False
    
    # Voice mappings file path
    voice_mappings_file = os.path.join(voices_dir, "voice_mappings.json")
    
    # Check if voice mappings already exist and we're not forcing regeneration
    if os.path.exists(voice_mappings_file) and not force:
        log(f"Voice mappings file already exists at {voice_mappings_file}. Use --force to regenerate.")
        return True
        
    # Load characters
    with open(characters_file, "r", encoding="utf-8") as f:
        characters = json.load(f)
    
    # OpenAI voice options
    openai_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    
    # Create default voice mappings
    voice_mappings = {}
    
    # Add narrator first
    voice_mappings["Narrator"] = {
        "openai": "onyx",  # Deeper voice for narrator
        "cartesia": "en_male_neutral"  # Default Cartesia male voice
    }
    
    # Simple voice assignment - cycle through available voices for variety
    voice_index = 0
    
    # Create mapping for each character
    for char_name, char_data in characters.items():
        # Skip if already processed (e.g., narrator)
        if char_name in voice_mappings:
            continue
            
        # Get gender from character data if available
        gender = char_data.get("gender", "").lower()
        is_male = "male" in gender
        is_female = "female" in gender
        
        # Determine OpenAI voice based on gender and available voices
        if is_male:
            openai_voice = "echo" if voice_index % 2 == 0 else "fable"
            cartesia_voice = "en_male_neutral"
        elif is_female:
            openai_voice = "nova" if voice_index % 2 == 0 else "shimmer"
            cartesia_voice = "en_female_neutral"
        else:
            # Use a rotating voice if gender not specified
            openai_voice = openai_voices[voice_index % len(openai_voices)]
            cartesia_voice = "en_male_neutral" if voice_index % 2 == 0 else "en_female_neutral"
        
        # Add to voice mappings
        voice_mappings[char_name] = {
            "openai": openai_voice,
            "cartesia": cartesia_voice
        }
        
        voice_index += 1
    
    # Save voice mappings
    with open(voice_mappings_file, "w", encoding="utf-8") as f:
        json.dump(voice_mappings, f, indent=2)
    
    log(f"Created voice mappings for {len(voice_mappings)} characters at {voice_mappings_file}")
    return True


def validate_voice_mappings(voice_mappings, character_list):
    """
    Validate that voice mappings exist for all characters with the current provider.

    Args:
        voice_mappings (dict): Dictionary of character -> provider -> voice_id mappings
        character_list (list): List of character names to validate

    Returns:
        bool: True if all characters have voice mappings, False otherwise
    """
    provider = os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()
    log(f"Validating voice mappings for provider: {provider}")

    # Debug log for validating characters
    log(f"Characters to validate: {character_list[:5]}... ({len(character_list)} total)", level="DEBUG")
    log(f"Voice mappings keys: {list(voice_mappings.keys())}", level="DEBUG")

    # Check for default voice
    default_voice = None
    for key in ["DEFAULT", "default"]:
        if key in voice_mappings and provider in voice_mappings[key]:
            default_voice = voice_mappings[key][provider]
            log(f"Found default voice: {default_voice}")
            break

    if not default_voice:
        log("WARNING: No default voice found. Some characters may be missing voice assignments.", level="WARNING")

    # Check each character
    missing_voices = []
    for character in character_list:
        voice_id = get_voice_id(character, voice_mappings)
        if not voice_id:
            missing_voices.append(character)

    if missing_voices:
        log(f"WARNING: {len(missing_voices)} characters are missing voice mappings for provider '{provider}':", level="WARNING")
        for i, character in enumerate(missing_voices[:10]):  # Show first 10 only
            log(f"  {i+1}. {character}", level="WARNING")

        if len(missing_voices) > 10:
            log(f"  ... and {len(missing_voices) - 10} more", level="WARNING")

        log(f"Please update your voice_mappings.json file with '{provider}' voices for these characters.", level="WARNING")
        return False

    log(f"All {len(character_list)} characters have voice mappings for provider '{provider}'")
    return True

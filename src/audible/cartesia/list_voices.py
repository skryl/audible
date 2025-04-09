"""
Module for listing available Cartesia voices.
"""

import os
import json
import argparse
from cartesia import Cartesia
from audible.utils.common import log

def get_cartesia_voices(limit=100, is_owner=False, is_starred=False, gender=None, output_file=None):
    """Get a list of all available voices from Cartesia API."""
    log("Fetching available voices from Cartesia API...")

    try:
        # Initialize Cartesia client
        api_key = os.getenv("CARTESIA_API_KEY")
        if not api_key:
            log("Error: CARTESIA_API_KEY not found in environment variables", level="ERROR")
            return None

        client = Cartesia(api_key=api_key)

        # Prepare API parameters
        params = {
            "limit": min(max(limit, 1), 100)  # Ensure limit is between 1 and 100
        }

        if is_owner:
            params["is_owner"] = True

        if is_starred:
            params["is_starred"] = True

        if gender:
            params["gender"] = gender

        # Fetch voices with parameters
        voices = client.voices.list(**params)

        # Process and format voice information
        voice_data = []
        # voices is a SyncPager object that we can iterate directly
        for voice in voices:
            # Extract data safely with fallbacks
            voice_info = {
                "id": voice.id,
                "name": voice.name,
                "language": getattr(voice, 'language', 'unknown'),
                "description": getattr(voice, 'description', '')
            }

            voice_data.append(voice_info)

        log(f"Found {len(voice_data)} voices")

        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(voice_data, f, indent=2)
            log(f"Saved voice information to {output_file}")

        return voice_data

    except Exception as e:
        log(f"Error fetching Cartesia voices: {e}", level="ERROR")
        return None

def display_voices(voices):
    """Display voice information in a formatted table."""
    if not voices:
        log("No voices to display", level="WARNING")
        return

    log(f"Displaying {len(voices)} voices:")

    # Print header
    print("\n{:<36} {:<30} {:<10} {:<}".format(
        "Voice ID", "Name", "Language", "Description"))
    print("-" * 100)

    # Print each voice
    for voice in voices:
        # Truncate description if too long
        description = voice["description"]
        if len(description) > 40:
            description = description[:37] + "..."

        print("{:<36} {:<30} {:<10} {:<}".format(
            voice["id"],
            voice["name"],
            voice["language"],
            description
        ))
    print()

def find_voices(voices, search_terms, output_file=None):
    """Find voices with specific terms."""
    if not voices:
        log("No voices to search", level="WARNING")
        return None

    matches = []
    for voice in voices:
        name = voice.get("name", "").lower()
        desc = voice.get("description", "").lower()

        if any(term in name or term in desc for term in search_terms):
            matches.append(voice)

    log(f"Found {len(matches)} voices matching search terms: {', '.join(search_terms)}")

    if output_file and matches:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2)
        log(f"Saved matching voices to {output_file}")

    return matches

def list_voices(output=None, gender=None, limit=100, is_owner=False, is_starred=False, search=None):
    """Main function to list Cartesia voices with filtering options."""
    log("Starting Cartesia voice listing")

    # Get voices from Cartesia API
    voices = get_cartesia_voices(
        limit=limit,
        is_owner=is_owner,
        is_starred=is_starred,
        gender=gender,
        output_file=output
    )

    if not voices:
        return None

    # Find voices by accent if requested
    if search:
        search_terms = [term.strip().lower() for term in search.split(',')]
        search_voices = find_voices(voices, search_terms,
                                              f"{output.split('.')[0]}_search.json" if output else None)
        if search_voices:
            display_voices(search_voices)
            return search_voices


    # Display voices
    display_voices(voices)

    log("Voice listing complete")
    return voices
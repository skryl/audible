"""
Character extraction for Audible.

This module provides functionality for extracting character information from book chapters.
"""

import os
import json
from audible.utils.common import (
    log, get_prompt, extract_chapter_num, get_chapter_filename
)
from audible.core.ai import call_llm_api, call_llm_api_async
from audible.utils.thread_pool import process_batch_async, process_in_parallel

def extract_characters(book_dir, force=False):
    """
    Extract and process character information from book chapters.

    This function should be run AFTER analyze_chapters to create:
    1. Character profiles in {book_dir}/characters/
    2. A consolidated characters.json file in {book_dir}/characters/

    Args:
        book_dir (str): Directory containing the book data
        force (bool): Force character extraction even if characters exist

    Returns:
        bool: True if successful, False otherwise
    """
    log(f"Extracting character information for book in {book_dir}")

    # Check for chapter analysis files
    analysis_dir = os.path.join(book_dir, "analysis")
    if not os.path.exists(analysis_dir):
        log(f"Analysis directory not found at {analysis_dir}. Run analyze_chapters first.", level="ERROR")
        return False

    # Create characters directory if it doesn't exist
    characters_dir = os.path.join(book_dir, "characters")
    if not os.path.exists(characters_dir):
        os.makedirs(characters_dir)
        log(f"Created characters directory at {characters_dir}")

    # Character output file - now in the characters directory
    characters_file = os.path.join(characters_dir, "characters.json")

    # Skip if characters file exists and we're not forcing regeneration
    if os.path.exists(characters_file) and not force:
        log(f"Characters file already exists at {characters_file}. Use --force to regenerate.")
        return True

    # Get the list of analysis files
    analysis_files = sorted([f for f in os.listdir(analysis_dir) if f.endswith("_analysis.json")])
    if not analysis_files:
        log(f"No analysis files found in {analysis_dir}. Run analyze_chapters first.", level="ERROR")
        return False

    log(f"Found {len(analysis_files)} analysis files")

    # Get the list of chapter files for chapter text
    chapters_dir = os.path.join(book_dir, "chapters")
    if not os.path.exists(chapters_dir):
        log(f"Chapters directory not found at {chapters_dir}", level="ERROR")
        return False

    chapter_files = sorted([f for f in os.listdir(chapters_dir) if f.endswith(".txt")])
    if not chapter_files:
        log(f"No chapter files found in {chapters_dir}", level="ERROR")
        return False

    log(f"Found {len(chapter_files)} chapter files")

    # Calculate padding digits based on total number of chapters
    num_chapters = len(chapter_files)

    # Track important characters across all chapters
    major_characters = {}  # Map of character name to appearance data

    # First, collect major characters from analysis files
    for analysis_file in analysis_files:
        analysis_path = os.path.join(analysis_dir, analysis_file)

        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)

            # Extract chapter number from filename
            chapter_num_parts = analysis_file.split("_")
            chapter_num = None
            for part in chapter_num_parts:
                if part.isdigit():
                    chapter_num = int(part)
                    break

            if chapter_num is None:
                log(f"Could not extract chapter number from analysis file: {analysis_file}", level="WARNING")
                continue

            # Extract major characters from the analysis
            if "major_characters" in analysis_data:
                log(f"Loading major characters from analysis file for chapter {chapter_num}")
                for character_name in analysis_data["major_characters"]:
                    # Initialize character if not already in the dictionary
                    if character_name not in major_characters:
                        major_characters[character_name] = {
                            "name": character_name,
                            "chapters": []
                        }

                    # Add chapter to character's appearance list
                    if chapter_num not in major_characters[character_name].get("chapters", []):
                        major_characters[character_name].setdefault("chapters", []).append(chapter_num)
            elif "characters" in analysis_data:
                log(f"No major_characters field found, using all characters from chapter {chapter_num}")
                for character_name in analysis_data["characters"]:
                    # Initialize character if not already in the dictionary
                    if character_name not in major_characters:
                        major_characters[character_name] = {
                            "name": character_name,
                            "chapters": []
                        }

                    # Add chapter to character's appearance list
                    if chapter_num not in major_characters[character_name].get("chapters", []):
                        major_characters[character_name].setdefault("chapters", []).append(chapter_num)
        except Exception as e:
            log(f"Error reading analysis file {analysis_file}: {e}", level="WARNING")

    # Get detailed information about each major character
    log(f"Found {len(major_characters)} major characters across all chapters")

    # Prepare chapter processing items
    chapters_to_process = []
    for chapter_file in chapter_files:
        # Extract chapter number from filename using utility function
        chapter_num = extract_chapter_num(chapter_file)
        if chapter_num is None:
            continue

        # Get the characters that appear in this chapter
        characters_in_chapter = [name for name, info in major_characters.items()
                             if chapter_num in info.get("chapters", [])]

        # Skip if no major characters in this chapter
        if not characters_in_chapter:
            log(f"No major characters found for chapter {chapter_num}")
            continue

        chapter_path = os.path.join(chapters_dir, chapter_file)
        chapters_to_process.append({
            'chapter_num': chapter_num,
            'chapter_path': chapter_path,
            'characters_in_chapter': characters_in_chapter,
            'characters_dir': characters_dir,
            'major_characters': major_characters.copy()  # Pass a copy of the current character data
        })

    # Process chapters in parallel
    log(f"Processing {len(chapters_to_process)} chapters in parallel for character extraction")
    if chapters_to_process:
        results = process_batch_async(
            chapters_to_process,
            process_chapter_characters
        )

        # Merge updated character information
        updated_character_data = {}
        for result in results:
            if result and 'updated_characters' in result:
                for name, info in result['updated_characters'].items():
                    if name not in updated_character_data:
                        updated_character_data[name] = info
                    else:
                        # Merge character information
                        for key, value in info.items():
                            if key == 'chapters':
                                # Merge chapter lists
                                updated_character_data[name]['chapters'] = list(set(
                                    updated_character_data[name].get('chapters', []) + value
                                ))
                            elif key not in updated_character_data[name] or not updated_character_data[name][key]:
                                updated_character_data[name][key] = value

        # Update the main character dictionary
        for name, info in updated_character_data.items():
            if name in major_characters:
                for key, value in info.items():
                    if key == 'chapters':
                        # Ensure chapters are unique
                        major_characters[name]['chapters'] = list(set(major_characters[name].get('chapters', []) + value))
                    elif key not in major_characters[name] or not major_characters[name][key]:
                        major_characters[name][key] = value

    # Save consolidated character information for major characters
    with open(characters_file, "w", encoding="utf-8") as f:
        json.dump(major_characters, f, indent=2)
    log(f"Saved consolidated character data to {characters_file} with {len(major_characters)} major characters")

    log("Character extraction complete")
    return True

async def process_chapter_characters(item):
    """
    Process a single chapter to extract detailed character information.

    Args:
        item: Dictionary containing chapter information

    Returns:
        Dictionary with updated character information
    """
    chapter_num = item['chapter_num']
    chapter_path = item['chapter_path']
    characters_in_chapter = item['characters_in_chapter']
    characters_dir = item['characters_dir']
    major_characters = item.get('major_characters', {})

    updated_characters = {}

    try:
        with open(chapter_path, "r", encoding="utf-8") as f:
            chapter_text = f.read()

        log(f"Performing detailed character analysis for chapter {chapter_num}")

        # Prepare character focus text
        character_focus = f"Focus on these major characters that appear in this chapter: {', '.join(characters_in_chapter)}."

        # Get character information from LLM using prompts.json
        system_message, prompt = get_prompt(
            "character_traits_extraction",
            {
                "chapter_num": chapter_num,
                "chapter_text": chapter_text,
                "character_focus": character_focus
            }
        )

        if not prompt:
            log(f"Character extraction prompt not found in prompts.json for chapter {chapter_num}", level="ERROR")
            return {'updated_characters': {}}

        # Use the async version of the LLM API call
        characters_response = await call_llm_api_async(prompt, system_message)

        try:
            # Parse the response as JSON
            chapter_characters = json.loads(characters_response)

            # Process each character and write to file immediately
            for name, info in chapter_characters.items():
                if name in characters_in_chapter:
                    # Update with chapter number
                    if 'chapters' not in info:
                        info['chapters'] = []
                    if chapter_num not in info['chapters']:
                        info['chapters'].append(chapter_num)

                    # Merge with existing data if available
                    if name in major_characters:
                        existing_info = major_characters[name]
                        # Keep existing chapters
                        if 'chapters' in existing_info:
                            info['chapters'] = list(set(info['chapters'] + existing_info['chapters']))

                    # Create a safe filename from the character name
                    safe_name = "".join(c if c.isalnum() else "_" for c in name).lower()
                    char_file = os.path.join(characters_dir, f"{safe_name}.json")

                    # Write to file immediately
                    with open(char_file, "w", encoding="utf-8") as f:
                        json.dump(info, f, indent=2)
                    log(f"Saved character data for {name} from chapter {chapter_num}")

                    # Add to updated characters dictionary
                    updated_characters[name] = info

            return {'updated_characters': updated_characters}
        except json.JSONDecodeError:
            log(f"Error parsing character data from chapter {chapter_num}: Invalid JSON", level="ERROR")
            return {'updated_characters': {}}

    except Exception as e:
        log(f"Error processing character data from chapter {chapter_num}: {e}", level="ERROR")
        return {'updated_characters': {}}

def parse_characters_response(response):
    """Parse the LLM response to extract character information."""
    characters = {}

    # Basic parsing: This should be improved based on the actual LLM response format
    try:
        # Try parsing as JSON first
        return json.loads(response)
    except json.JSONDecodeError:
        # If not JSON, try a simple parsing approach
        lines = response.strip().split("\n")
        current_character = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a new character name
            if line.endswith(":") and not line.startswith("-"):
                current_character = line[:-1].strip()
                characters[current_character] = {"name": current_character}
            elif current_character and ":" in line:
                # Parse attribute: value pairs
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                if key in ["gender", "age", "description", "personality", "voice", "appearance"]:
                    characters[current_character][key] = value

    return characters

def find_character_sample(text, character_name):
    """Find a sample text where the character appears."""
    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        if character_name in paragraph:
            # Return a sample of reasonable length
            if len(paragraph) > 500:
                # Find the position of the character name
                pos = paragraph.find(character_name)
                start = max(0, pos - 100)
                end = min(len(paragraph), pos + 400)
                return paragraph[start:end]
            return paragraph

    return ""
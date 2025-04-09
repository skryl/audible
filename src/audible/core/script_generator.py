"""
Script generation for Audible.

This module provides functionality for generating TTS scripts from chapter text files.
"""

import os
import json
from audible.utils.common import (
    log, get_prompt, extract_chapter_num, get_chapter_filename
)
from audible.core.ai import call_llm_api, call_llm_api_async
from audible.core.formatters import format_script
from audible.utils.thread_pool import process_batch_async, process_in_parallel

def generate_scripts(book_dir, force=False):
    """
    Generate TTS scripts based on raw chapter text files.

    Args:
        book_dir (str): Directory containing the book data
        force (bool): Force regeneration of scripts even if they exist

    Returns:
        bool: True if successful, False otherwise
    """
    log(f"Generating scripts for book in {book_dir}")

    # Create scripts directory if it doesn't exist
    scripts_dir = os.path.join(book_dir, "scripts")
    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)
        log(f"Created scripts directory at {scripts_dir}")

    # Characters directory path
    characters_dir = os.path.join(book_dir, "characters")

    # Check for character information in characters directory
    characters_file = os.path.join(characters_dir, "characters.json")

    global_characters = {}
    if os.path.exists(characters_file):
        try:
            with open(characters_file, "r", encoding="utf-8") as f:
                global_characters = json.load(f)
            log(f"Loaded consolidated character information with {len(global_characters)} characters")
        except Exception as e:
            log(f"Error loading character file {characters_file}: {e}", level="WARNING")
    else:
        log(f"Characters file not found at {characters_file}. Will use characters from analysis files if available.", level="WARNING")

    # Check for analysis directory
    analysis_dir = os.path.join(book_dir, "analysis")
    if not os.path.exists(analysis_dir):
        log(f"Analysis directory not found at {analysis_dir}. Character information may be limited.", level="WARNING")
        # Only proceed if we have the characters.json file
        if not global_characters:
            log(f"No character information available. Run extract_characters first.", level="ERROR")
            return False
    else:
        log(f"Using character information from analysis files where available")

    # Get the list of chapter files
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

    # Prepare chapters to process
    chapters_to_process = []

    for chapter_file in chapter_files:
        # Extract chapter number from filename using utility function
        chapter_num = extract_chapter_num(chapter_file)
        if chapter_num is None:
            continue

        # Get the script filename using the utility function
        script_file = get_chapter_filename(
            book_dir, chapter_num, 'script', num_chapters=num_chapters
        )

        # Skip if script exists and we're not forcing regeneration
        if os.path.exists(script_file) and not force:
            log(f"Script for chapter {chapter_num} already exists. Use --force to regenerate.")
            continue

        # Try to get character information from the corresponding analysis file
        analysis_file = get_chapter_filename(
            book_dir, chapter_num, 'analysis', num_chapters=num_chapters
        )

        chapter_specific_characters = {}
        character_list = []

        if os.path.exists(analysis_file):
            try:
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)

                if "characters" in analysis_data:
                    character_list = analysis_data["characters"]
                    log(f"Using {len(character_list)} characters from analysis file for chapter {chapter_num}")

                    # Merge with global characters data to get full character details
                    for char_name in character_list:
                        if char_name in global_characters:
                            chapter_specific_characters[char_name] = global_characters[char_name]
                        else:
                            # Just create a basic entry if not in global data
                            chapter_specific_characters[char_name] = {"name": char_name}
            except Exception as e:
                log(f"Error reading analysis file {analysis_file}: {e}", level="WARNING")

        # If we couldn't get character data from analysis, fall back to global data
        if not chapter_specific_characters:
            log(f"No character data in analysis file for chapter {chapter_num}. Using global character data.")
            chapter_specific_characters = global_characters

        chapter_path = os.path.join(chapters_dir, chapter_file)

        # Add to list of chapters to process
        chapters_to_process.append({
            'chapter_num': chapter_num,
            'chapter_path': chapter_path,
            'script_file': script_file,
            'characters': chapter_specific_characters
        })

    if not chapters_to_process:
        log("No chapters need script generation")
        return True

    # Process chapters in parallel
    log(f"Processing {len(chapters_to_process)} chapters in parallel for script generation")
    results = process_batch_async(
        chapters_to_process,
        process_chapter_script
    )

    # Check results
    success_count = sum(1 for result in results if result)
    log(f"Successfully generated scripts for {success_count} out of {len(chapters_to_process)} chapters")

    log("Script generation complete")
    return success_count > 0

async def process_chapter_script(item):
    """Process a single chapter to generate a script."""
    chapter_num = item['chapter_num']
    chapter_path = item['chapter_path']
    script_file = item['script_file']
    characters = item['characters']

    try:
        # Load chapter text directly
        with open(chapter_path, "r", encoding="utf-8") as f:
            chapter_text = f.read()

        log(f"Generating script for chapter {chapter_num}")

        # Generate the script using the LLM
        script = await generate_chapter_script(chapter_num, chapter_text, characters)

        # Save the script to file
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2)
        log(f"Saved script for chapter {chapter_num}")

        return True
    except Exception as e:
        log(f"Error generating script for chapter {chapter_num}: {e}", level="ERROR")
        return False

async def generate_chapter_script(chapter_num, chapter_text, characters):
    """Generate a TTS script for a single chapter directly from the chapter text."""
    log(f"Generating detailed script for chapter {chapter_num}")

    # Prepare character information for the prompt
    character_info = []
    for name, info in characters.items():
        char_desc = f"{name}: {info.get('gender', 'unknown')} - {info.get('description', '')}"
        character_info.append(char_desc)

    character_context = "\n".join(character_info)

    # Get script prompt from prompts.json
    system_message, prompt = get_prompt(
        "chapter_script_conversion",
        {
            "chapter_num": chapter_num,
            "character_list": ", ".join(characters.keys()),
            "chapter_text": chapter_text
        }
    )

    if not prompt:
        log(f"Script generation prompt not found in prompts.json for chapter {chapter_num}", level="ERROR")
        return {"chapter_number": chapter_num, "title": f"Chapter {chapter_num}", "segments": []}

    # Get the response from the LLM using the async version
    response = await call_llm_api_async(prompt, system_message)

    # Parse the response
    try:
        script_data = json.loads(response)
    except json.JSONDecodeError:
        # If the response is not valid JSON, try to format it
        script_data = format_script(response, chapter_num)

    # Add chapter metadata
    if isinstance(script_data, dict):
        script_data["chapter_number"] = chapter_num
        script_data["title"] = f"Chapter {chapter_num}"
    else:
        script_data = {
            "chapter_number": chapter_num,
            "title": f"Chapter {chapter_num}",
            "segments": script_data if isinstance(script_data, list) else []
        }

    return script_data
"""
Chapter analysis for Audible.

This module provides functionality for analyzing book chapters to identify scenes and characters.
"""

import os
import json
from audible.utils.common import (
    log, get_prompt, extract_chapter_num, get_padded_chapter_num,
    get_chapter_filename
)
from audible.utils.thread_pool import process_batch_async
from audible.core.ai import call_llm_api, call_llm_api_async

def analyze_chapters(book_dir, force=False):
    """
    Analyze chapters to identify scenes and characters.

    This function will create analysis files in {book_dir}/analysis/chapter_{n}_analysis.json
    containing scene information, character lists, and major characters.

    Args:
        book_dir (str): Directory containing the book data
        force (bool): Force reanalysis even if results exist

    Returns:
        bool: True if successful, False otherwise
    """
    # Check if we should use async processing
    use_async = os.environ.get("AUDIBLE_USE_ASYNC", "false").lower() == "true"
    
    log(f"Analyzing chapters for book in {book_dir}")

    # Check if analysis files already exist and we're not forcing regeneration
    analysis_dir = os.path.join(book_dir, "analysis")
    if not os.path.exists(analysis_dir):
        os.makedirs(analysis_dir)
        log(f"Created analysis directory at {analysis_dir}")

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

    # Filter out chapters that don't need processing
    chapters_to_process = []
    for chapter_file in chapter_files:
        chapter_num = extract_chapter_num(chapter_file)
        if chapter_num is None:
            log(f"Could not extract chapter number from filename: {chapter_file}", level="WARNING")
            continue

        chapter_analysis_file = get_chapter_filename(
            book_dir, chapter_num, 'analysis', num_chapters=num_chapters
        )

        # Skip if analysis exists and we're not forcing regeneration
        if os.path.exists(chapter_analysis_file) and not force:
            log(f"Analysis for chapter {chapter_num} already exists. Use --force to regenerate.")
            continue

        # Add to list of chapters to process
        chapters_to_process.append({
            'chapter_file': chapter_file,
            'chapter_num': chapter_num,
            'chapters_dir': chapters_dir,
            'analysis_dir': analysis_dir,
            'chapter_analysis_file': chapter_analysis_file
        })

    if not chapters_to_process:
        log("No chapters need processing")
        return True

    log(f"Processing {len(chapters_to_process)} chapters in parallel")

    # Create a function that returns the coroutine directly for process_async to handle
    results = process_batch_async(
        chapters_to_process,
        # Just return the coroutine for process_async to await
        process_chapter
    )

    # Check results
    success_count = sum(1 for result in results if result)
    log(f"Successfully processed {success_count} out of {len(chapters_to_process)} chapters")

    return success_count > 0

async def process_chapter(item):
    chapter_file = item['chapter_file']
    chapter_num = item['chapter_num']
    chapters_dir = item['chapters_dir']
    analysis_dir = item['analysis_dir']
    chapter_analysis_file = item['chapter_analysis_file']
    
    """Process a single chapter to generate scene and character analysis."""
    try:
        chapter_path = os.path.join(chapters_dir, chapter_file)
        with open(chapter_path, "r", encoding="utf-8") as f:
            chapter_text = f.read()

        log(f"Analyzing chapter {chapter_num}")

        # STEP 1: Get scene breakdown from LLM
        system_message, prompt = get_prompt(
            "chapter_scene_breakdown",
            {"chapter_num": chapter_num, "chapter_text": chapter_text}
        )

        if not prompt:
            log(f"Scene breakdown prompt not found in prompts.json for chapter {chapter_num}", level="ERROR")
            return False

        analysis_response = await call_llm_api_async(prompt, system_message)

        # Parse the response
        chapter_analysis = parse_analysis_response(analysis_response)

        # Extract characters from scene analysis
        scene_characters = extract_characters_from_scenes(chapter_analysis)

        # STEP 2: Use combined character extraction
        system_message, character_prompt = get_prompt(
            "chapter_character_extraction",
            {"chapter_num": chapter_num, "chapter_text": chapter_text}
        )

        if not character_prompt:
            log(f"Combined character extraction prompt not found in prompts.json for chapter {chapter_num}", level="ERROR")
            # Fall back to scene characters
            all_chapter_characters = scene_characters
            major_characters = scene_characters
        else:
            # Get both character lists
            characters_response = await call_llm_api_async(character_prompt, system_message)

            # Parse the JSON response
            try:
                character_data = json.loads(characters_response)
                all_characters_from_llm = character_data.get("all_characters", [])
                major_characters = character_data.get("major_characters", [])

                # Combine scene characters with all characters from LLM
                all_chapter_characters = list(set(scene_characters + all_characters_from_llm))

                log(f"Extracted {len(all_chapter_characters)} total characters and {len(major_characters)} major characters for chapter {chapter_num}")

                # Ensure all major characters are in all_characters list
                for char in major_characters:
                    if char not in all_chapter_characters:
                        all_chapter_characters.append(char)
            except json.JSONDecodeError:
                log(f"Error parsing combined character response as JSON for chapter {chapter_num}", level="WARNING")
                # Use scene characters as fallback
                all_chapter_characters = scene_characters
                major_characters = scene_characters

        # Add characters lists to the analysis data
        chapter_analysis["characters"] = all_chapter_characters
        chapter_analysis["major_characters"] = major_characters

        # Save complete analysis to file
        with open(chapter_analysis_file, "w", encoding="utf-8") as f:
            json.dump(chapter_analysis, f, indent=2)
        log(f"Saved analysis for chapter {chapter_num} with {len(all_chapter_characters)} characters and {len(major_characters)} major characters")

        return True
    except Exception as e:
        log(f"Error processing chapter {chapter_num}: {e}", level="ERROR")
        return False

def extract_characters_from_scenes(analysis):
    """Extract character names from scene analysis."""
    characters = set()

    # Extract from scenes
    for scene in analysis.get("scenes", []):
        for character in scene.get("characters", []):
            if character and character.strip() and character.lower() != "none":
                characters.add(character.strip())

    return list(characters)

def parse_character_list(response):
    """Parse a comma-separated list of character names."""
    characters = set()

    # Clean up the response and split by commas
    if response:
        # Remove common prefixes like "Characters:" or "The characters are:"
        if ":" in response:
            response = response.split(":", 1)[1]

        # Split by commas and clean up
        for name in response.split(","):
            name = name.strip()
            if name and name.lower() not in ["narrator", "narration", "none"]:
                characters.add(name)

    return list(characters)

def parse_analysis_response(response):
    """Parse the LLM response to extract chapter analysis."""
    # Basic implementation - should be improved based on the actual LLM response format
    try:
        # Try parsing as JSON first
        return json.loads(response)
    except json.JSONDecodeError:
        # If not JSON, use a simple scene extraction approach
        scenes = []
        scene_num = 0
        current_scene = None

        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for scene indicators
            if line.lower().startswith("scene") or "scene" in line.lower() and ":" in line:
                scene_num += 1
                current_scene = {
                    "scene_number": scene_num,
                    "characters": [],
                    "location": "",
                    "summary": ""
                }
                scenes.append(current_scene)

                # Try to extract summary from the scene line
                parts = line.split(":", 1)
                if len(parts) > 1:
                    current_scene["summary"] = parts[1].strip()

            # Add information to the current scene
            elif current_scene:
                if "character" in line.lower() and ":" in line:
                    _, chars = line.split(":", 1)
                    current_scene["characters"] = [c.strip() for c in chars.split(",")]
                elif "location" in line.lower() and ":" in line:
                    _, loc = line.split(":", 1)
                    current_scene["location"] = loc.strip()
                elif "summary" in line.lower() and ":" in line:
                    _, summary = line.split(":", 1)
                    current_scene["summary"] = summary.strip()
                elif not any(key in current_scene for key in ["characters", "location", "summary"]):
                    # If we haven't assigned any information yet, use this as the summary
                    current_scene["summary"] = line

        return {"scenes": scenes}
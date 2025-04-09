"""
Formatter module for formatting output files.
"""

from audible.utils.common import log
import json

def format_character_file(description):
    """Format a character description for output to a file."""
    if not description:
        log("No character description to format", level="WARNING")
        return "No character description available."

    try:
        # Extract data from the character description
        name = description.get("name", "Unknown")
        traits = description.get("personality_traits", [])
        appearance = description.get("appearance", "")
        voice = description.get("voice_traits", {})
        relationships = description.get("relationships", {})
        quotes = description.get("notable_quotes", [])

        # Format the personality traits as bullet points
        traits_formatted = "\n".join([f"- {trait}" for trait in traits])

        # Format the voice traits
        voice_formatted = ""
        if isinstance(voice, dict):
            for trait_type, trait_value in voice.items():
                voice_formatted += f"- **{trait_type}**: {trait_value}\n"
        else:
            voice_formatted = voice  # Handle if it's a string

        # Format relationships as bullet points
        relationships_formatted = ""
        if isinstance(relationships, dict):
            for character, relationship in relationships.items():
                relationships_formatted += f"- **{character}**: {relationship}\n"
        else:
            relationships_formatted = relationships  # Handle if it's a string

        # Format quotes as bullet points
        quotes_formatted = "\n".join([f"- \"{quote}\"" for quote in quotes])

        # Combine all the parts into a markdown document
        markdown = f"""# {name}

## Personality Traits

{traits_formatted}

## Appearance

{appearance}

## Voice Characteristics

{voice_formatted}

## Relationships

{relationships_formatted}

## Notable Quotes

{quotes_formatted}
"""
        return markdown
    except Exception as e:
        log(f"Error formatting character file: {e}", level="ERROR")
        return f"Error formatting character description: {str(e)}"

def format_chapter_file(chapter_num, chapter_analysis):
    """Format chapter analysis for output to a file."""
    if not chapter_analysis:
        log(f"No analysis available for Chapter {chapter_num}", level="WARNING")
        return f"# Chapter {chapter_num}\n\nNo analysis available."

    try:
        # Extract data from the chapter analysis
        summary = chapter_analysis.get("summary", "No summary available.")
        characters = chapter_analysis.get("characters_present", [])
        interactions = chapter_analysis.get("character_interactions", {})

        # Format the characters present as bullet points
        characters_formatted = "\n".join([f"- {character}" for character in characters])

        # Format interactions as bullet points with character names as subheadings
        interactions_formatted = ""
        if isinstance(interactions, dict):
            for character, interaction in interactions.items():
                interactions_formatted += f"### {character}\n\n{interaction}\n\n"
        else:
            interactions_formatted = interactions  # Handle if it's a string

        # Combine all the parts into a markdown document
        markdown = f"""# Chapter {chapter_num}

## Summary

{summary}

## Characters Present

{characters_formatted}

## Character Interactions

{interactions_formatted}
"""
        return markdown
    except Exception as e:
        log(f"Error formatting chapter file: {e}", level="ERROR")
        return f"# Chapter {chapter_num}\n\nError formatting chapter analysis: {str(e)}"

def format_script(response, chapter_num):
    """Format a script response from the LLM that isn't in JSON format."""
    log(f"Formatting non-JSON script response for chapter {chapter_num}")

    try:
        # Try to extract JSON from the response if it's wrapped in backticks or other text
        if "```json" in response:
            json_part = response.split("```json")[1].split("```")[0].strip()
            return json.loads(json_part)

        # If we can't parse as JSON, create a simple script structure
        segments = []
        current_segment = None

        # Simple line-by-line parsing
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check for segment markers
            if line.startswith("NARRATOR:") or line.startswith("NARRATION:"):
                # Create a new narration segment
                text = line.split(":", 1)[1].strip()
                current_segment = {
                    "type": "narration",
                    "text": text
                }
                segments.append(current_segment)
            elif ":" in line and not line.startswith("{") and not line.startswith("["):
                # This looks like a character dialogue
                speaker, text = line.split(":", 1)
                speaker = speaker.strip()
                text = text.strip()

                # Check for emotion in parentheses
                emotion = "neutral"
                if "(" in speaker and ")" in speaker:
                    parts = speaker.split("(", 1)
                    speaker = parts[0].strip()
                    emotion = parts[1].split(")", 1)[0].strip()

                current_segment = {
                    "type": "dialogue",
                    "character": speaker,
                    "text": text,
                    "emotion": emotion
                }
                segments.append(current_segment)
            elif current_segment:
                # This is a continuation of the previous segment
                current_segment["text"] += " " + line

        return segments

    except Exception as e:
        log(f"Error formatting script response: {e}", level="ERROR")
        # Return a minimal script with an error message
        return [{
            "type": "narration",
            "text": f"Error formatting script response: {str(e)}"
        }]

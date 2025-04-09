"""
Text processing module for handling book text.
"""

import re
import time
from audible.utils.common import log

def read_book(file_path):
    """Read a book from a file."""
    log(f"Reading file: {file_path}")
    start_time = time.time()
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    file_size_mb = len(content) / 1024 / 1024
    log(f"Read {file_size_mb:.2f} MB from {file_path} in {time.time() - start_time:.2f} seconds")
    return content

def clean_text(text):
    """Clean up the text by removing headers, footers, etc."""
    log("Cleaning text...")
    start_time = time.time()
    # Remove Project Gutenberg header and footer
    start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"

    if start_marker in text:
        text = text.split(start_marker)[1]
        log("Removed Project Gutenberg header")
    if end_marker in text:
        text = text.split(end_marker)[0]
        log("Removed Project Gutenberg footer")

    clean_text = text.strip()
    log(f"Text cleaned in {time.time() - start_time:.2f} seconds")
    return clean_text

def extract_chapters(text):
    """Extract chapters from the book text."""
    log("Extracting chapters...")
    start_time = time.time()
    # Extract chapters based on chapter markers
    chapter_pattern = r'CHAPTER [IVXLCDM]+\.'
    chapters = re.split(chapter_pattern, text)

    # Remove the preface and other non-chapter content
    if "THE PREFACE" in chapters[0]:
        chapters[0] = chapters[0].split("THE PREFACE")[0]
        log("Removed preface from text")

    # Cleanup and return only valid chapters
    chapters = [ch.strip() for ch in chapters if len(ch.strip()) > 100]
    log(f"Found {len(chapters)} chapters in {time.time() - start_time:.2f} seconds")
    return chapters

def split_script_for_tts(script_text):
    """Split a script into individual lines for TTS processing."""
    log("Splitting script for TTS...")

    # Split by newlines
    lines = script_text.strip().split('\n')

    # Process each line to identify speakers and text
    processed_lines = []
    current_speaker = "DEFAULT"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is a speaker line
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2 and parts[0].upper() == parts[0]:  # Speaker names are all caps
                speaker = parts[0].strip()
                text = parts[1].strip()
                # Skip empty text
                if not text:
                    continue

                current_speaker = speaker
                processed_lines.append({"speaker": speaker, "text": text})
            else:
                # This is a line with a colon but not a speaker transition
                processed_lines.append({"speaker": current_speaker, "text": line})
        else:
            # This is a continuation of the current speaker
            processed_lines.append({"speaker": current_speaker, "text": line})

    log(f"Split script into {len(processed_lines)} lines")
    return processed_lines

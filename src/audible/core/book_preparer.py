"""
Book preparation for Audible.

This module provides functionality for preparing books by splitting them into chapters.
"""

import os
import re
import string
from audible.utils.common import (
    log, calculate_padding_digits, get_padded_chapter_num
)

def prepare_book(book_dir, force=False):
    """
    Prepare a book by splitting it into chapters and cleaning up the text.

    Args:
        book_dir (str): Directory containing the book data with a book.txt file
        force (bool): Force regeneration of chapter files even if they exist

    Returns:
        bool: True if successful, False otherwise
    """
    log(f"Preparing book in {book_dir}")

    # Check if book.txt exists
    book_file = os.path.join(book_dir, "book.txt")
    if not os.path.exists(book_file):
        log(f"Book file not found at {book_file}", level="ERROR")
        return False

    # Create chapters directory if it doesn't exist
    chapters_dir = os.path.join(book_dir, "chapters")
    if not os.path.exists(chapters_dir):
        os.makedirs(chapters_dir)
        log(f"Created chapters directory at {chapters_dir}")
    elif force:
        # If force flag is set, remove existing chapter files
        log("Force flag set, removing existing chapter files...")
        for file in os.listdir(chapters_dir):
            if file.endswith(".txt"):
                os.remove(os.path.join(chapters_dir, file))
        log("Existing chapter files removed")

    # Load the book text
    with open(book_file, "r", encoding="utf-8") as f:
        book_text = f.read()

    log(f"Loaded book text ({len(book_text)} characters)")

    # Split the book into chapters
    chapters = split_into_chapters(book_text)

    if not chapters:
        log("Failed to identify chapters in the book", level="ERROR")
        return False

    log(f"Identified {len(chapters)} chapters")

    # Calculate the number of digits needed for padding
    num_chapters = len(chapters)
    padding_digits = calculate_padding_digits(num_chapters)
    log(f"Using {padding_digits} digits for chapter number padding")

    # Process and save each chapter
    existing_chapters = False
    for i, (title, content) in enumerate(chapters):
        chapter_num = i + 1
        # Pad the chapter number with leading zeros using utility function
        padded_chapter_num = get_padded_chapter_num(chapter_num, padding_digits)
        chapter_file = os.path.join(chapters_dir, f"{padded_chapter_num}_{clean_filename(title)}.txt")

        # Check if chapter file already exists and we're not forcing regeneration
        if os.path.exists(chapter_file) and not force:
            existing_chapters = True
            continue

        # Clean up the chapter text
        cleaned_content = clean_chapter_text(content)

        # Verify content length
        log(f"Chapter {padded_chapter_num}: {title} - {len(cleaned_content)} characters")

        # Save the chapter
        with open(chapter_file, "w", encoding="utf-8") as f:
            f.write(cleaned_content)

        log(f"Saved chapter {padded_chapter_num}: {title}")

    if existing_chapters and not force:
        log("Some chapter files already exist. Use --force to regenerate.", level="WARNING")

    log("Book preparation complete")
    return True

def split_into_chapters(text):
    """
    Split book text into chapters based on common chapter patterns.

    Args:
        text (str): The full book text

    Returns:
        list: List of (chapter_title, chapter_content) tuples
    """
    # Try various common chapter heading patterns
    patterns = [
        # CHAPTER I, CHAPTER 1, Chapter I, Chapter 1
        r'(?i)CHAPTER\s+([IVXLCDM\d]+)[.\s]*(?:\n+|:)(.+?)(?=CHAPTER\s+[IVXLCDM\d]+|\Z)',
        # I., II., 1., 2.
        r'(?m)^([IVXLCDM\d]+)[.\s]*\n+(.+?)(?=^[IVXLCDM\d]+[.\s]*$|\Z)',
        # "Chapter One", "Chapter Two"
        r'(?i)Chapter\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Eleven|Twelve)[.\s]*(?:\n+|:)(.+?)(?=Chapter\s+|\Z)'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        if matches and len(matches) > 1:  # At least 2 chapters to be valid
            # Filter out empty or very short content (likely from table of contents)
            valid_chapters = []
            for chapter_num, content in matches:
                # Skip chapters with very short content (likely TOC entries)
                if len(content.strip()) > 500:  # Threshold for minimum chapter length
                    valid_chapters.append(("Chapter " + chapter_num, content.strip()))

            # Only use this pattern if we found actual chapters
            if len(valid_chapters) > 1:
                return valid_chapters

    # If no pattern worked, try to split by blank lines and headings
    paragraphs = text.split("\n\n")
    chapters = []
    current_chapter = []
    current_title = "Chapter 1"

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if this looks like a chapter heading
        if len(para) < 50 and any(x in para.lower() for x in ["chapter", "book ", "part "]):
            # Save previous chapter if any
            if current_chapter and len("\n\n".join(current_chapter)) > 500:
                chapters.append((current_title, "\n\n".join(current_chapter)))

            # Start new chapter
            current_title = para
            current_chapter = []
        else:
            current_chapter.append(para)

    # Add the last chapter
    if current_chapter and len("\n\n".join(current_chapter)) > 500:
        chapters.append((current_title, "\n\n".join(current_chapter)))

    # If we identified chapters, return them
    if len(chapters) > 1:
        return chapters

    # Last resort: just split into ~10 equal parts
    if len(text) > 5000:  # Only if text is long enough
        chunk_size = len(text) // 10
        chunks = []

        for i in range(0, 10):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < 9 else len(text)
            chunk = text[start:end]
            # Try to start and end at paragraph boundaries
            if i > 0 and start > 0:
                first_newline = chunk.find("\n\n")
                if first_newline > 0:
                    chunk = chunk[first_newline+2:]
            chunks.append((f"Chapter {i+1}", chunk))

        return chunks

    # If all else fails, return the whole text as one chapter
    return [("Chapter 1", text)]

def clean_chapter_text(text):
    """
    Clean up chapter text by removing extra whitespace, fixing quotes, etc.

    Args:
        text (str): The chapter text to clean

    Returns:
        str: The cleaned chapter text
    """
    # Remove extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # Fix common OCR issues
    text = text.replace('—', '-')
    text = text.replace(''', "'")
    text = text.replace(''', "'")
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    text = text.replace('…', '...')

    return text.strip()

def clean_filename(text):
    """
    Clean up a string to use as a filename.

    Args:
        text (str): The text to clean

    Returns:
        str: The cleaned filename
    """
    # Remove invalid filename characters
    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    filename = ''.join(c for c in text if c in valid_chars)

    # Convert spaces to underscores and limit length
    filename = filename.replace(' ', '_')[:50].lower()

    return filename
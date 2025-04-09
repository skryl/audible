"""
Common utility functions for the Audible package.
"""

import os
import json
import time
import re
import difflib
from datetime import datetime
import tiktoken

def log(message, level="INFO"):
    """
    Log a message with timestamp based on the current log level.

    Args:
        message: The message to log
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Get the log level from environment variable, default to INFO
    current_level = os.getenv("AUDIBLE_LOG_LEVEL", "INFO").upper()

    # Define log level hierarchy
    log_levels = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3
    }

    # Only log if the message level is >= current level
    if log_levels.get(level.upper(), 1) >= log_levels.get(current_level, 1):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{level}] {timestamp} - {message}")

def get_token_count(text):
    """Count the number of tokens in the text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
        token_count = len(encoding.encode(text))
        return token_count
    except KeyError:
        # Fallback to cl100k_base encoding if model not found
        log("Model encoding not found, falling back to cl100k_base", level="WARNING")
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(text))
        return token_count

def truncate_to_token_limit(text, max_tokens):
    """Truncate text to fit within the token limit."""
    original_token_count = get_token_count(text)
    log(f"Checking if truncation needed: {original_token_count} tokens (limit: {max_tokens})")

    encoding = tiktoken.encoding_for_model("gpt-4o")
    tokens = encoding.encode(text)

    if len(tokens) <= max_tokens:
        return text

    # Truncate to the token limit
    log(f"Truncating text from {len(tokens)} to {max_tokens} tokens")
    truncated_tokens = tokens[:max_tokens]
    result = encoding.decode(truncated_tokens)
    log(f"Text truncated: {original_token_count - max_tokens} tokens removed")
    return result

def load_prompts(prompts_file="prompts.json"):
    """Load prompts from the JSON file."""
    try:
        # First try to load from the current directory
        if os.path.exists(prompts_file):
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
                log(f"Loaded prompts from {prompts_file}")
                return prompts

        # If not found, try to load from the package
        package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        package_prompts = os.path.join(package_dir, prompts_file)
        if os.path.exists(package_prompts):
            with open(package_prompts, 'r', encoding='utf-8') as f:
                prompts = json.load(f)
                log(f"Loaded prompts from {package_prompts}")
                return prompts

        log(f"Prompts file not found at {prompts_file} or {package_prompts}", level="ERROR")
        return {}
    except Exception as e:
        log(f"Error loading prompts: {e}", level="ERROR")
        log("Using default prompts", level="WARNING")
        return {}

def get_prompt(prompt_type, variables=None):
    """Get a prompt by type and fill in variables."""
    prompts = load_prompts()

    if prompt_type not in prompts:
        log(f"Prompt type '{prompt_type}' not found in prompts.json", level="ERROR")
        return None, None

    prompt_data = prompts[prompt_type]
    system_message = prompt_data.get("system_message", "")
    prompt_template = prompt_data.get("prompt", "")
    required_vars = prompt_data.get("variables", [])

    # Check if all required variables are provided
    if variables:
        for var in required_vars:
            if var not in variables:
                log(f"Required variable '{var}' not provided for prompt '{prompt_type}'", level="ERROR")
                return None, None

        # Replace variables in the system message
        if system_message:
            for var_name, var_value in variables.items():
                system_message = system_message.replace(f"{{{var_name}}}", str(var_value))

        # Replace variables in the prompt
        for var_name, var_value in variables.items():
            prompt_template = prompt_template.replace(f"{{{var_name}}}", str(var_value))

    return system_message, prompt_template

def slugify(text):
    """Convert a string to a slug for filenames."""
    # Remove special characters and replace spaces with underscores
    import re
    # Remove non-alpha characters and convert spaces to underscores
    slug = re.sub(r'[^a-zA-Z0-9 ]', '', text.lower()).strip().replace(' ', '_')
    return slug

def calculate_padding_digits(num_chapters):
    """Calculate the number of digits needed for chapter number padding."""
    return len(str(num_chapters))

def get_padded_chapter_num(chapter_num, padding_digits=None, num_chapters=None):
    """
    Return a chapter number padded with leading zeros.

    Args:
        chapter_num (int): The chapter number to pad
        padding_digits (int, optional): Number of digits to pad to
        num_chapters (int, optional): Total number of chapters (used to calculate padding if padding_digits not provided)

    Returns:
        str: Padded chapter number (e.g., '01', '02', etc.)
    """
    if padding_digits is None:
        if num_chapters is None:
            padding_digits = 2  # Default to 2 digits if no info provided
        else:
            padding_digits = calculate_padding_digits(num_chapters)

    return str(chapter_num).zfill(padding_digits)

def extract_chapter_num(filename):
    """
    Extract chapter number from a filename with padded numbers.

    Args:
        filename (str): Filename that starts with a padded chapter number (e.g., '01_chapter.txt')

    Returns:
        int: The chapter number as an integer, or None if no number found
    """
    chapter_num_match = re.match(r'^(\d+)_', filename)
    if chapter_num_match:
        return int(chapter_num_match.group(1))
    else:
        log(f"Could not extract chapter number from filename: {filename}", level="WARNING")
        return None

def get_chapter_filename(book_dir, chapter_num, file_type, padding_digits=None, num_chapters=None, provider=None):
    """
    Generate a standardized chapter filename for a given file type.

    Args:
        book_dir (str): Directory containing the book data
        chapter_num (int): The chapter number
        file_type (str): Type of file (e.g., 'analysis', 'script', 'tts')
        padding_digits (int, optional): Number of digits to pad chapter number to
        num_chapters (int, optional): Total number of chapters (used to calculate padding if padding_digits not provided)
        provider (str, optional): TTS provider (e.g., 'openai', 'cartesia') for tts and audio files

    Returns:
        str: Full path to the chapter file
    """

    num_chapters = len(os.listdir(os.path.join(book_dir, 'chapters')))
    padded_num = get_padded_chapter_num(chapter_num, padding_digits, num_chapters)

    # Get provider if it's needed but not provided
    if provider is None and file_type in ['tts', 'audio']:
        provider = os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()

    # Determine the appropriate directory and extension based on file type
    if file_type == 'chapter':
        return os.path.join(book_dir, 'chapters', f"{padded_num}_chapter.txt")
    elif file_type == 'analysis':
        return os.path.join(book_dir, 'analysis', f"chapter_{padded_num}_analysis.json")
    elif file_type == 'script':
        return os.path.join(book_dir, 'scripts', f"chapter_{padded_num}_script.json")
    elif file_type == 'tts':
        # Place TTS files in provider-specific subdirectory
        provider_dir = os.path.join(book_dir, 'tts', provider)
        os.makedirs(provider_dir, exist_ok=True)
        return os.path.join(provider_dir, f"chapter_{padded_num}_tts.json")
    elif file_type == 'audio':
        # Place audio files in provider-specific subdirectory
        provider_dir = os.path.join(book_dir, 'audio', provider)
        os.makedirs(provider_dir, exist_ok=True)
        return os.path.join(provider_dir, f"chapter_{padded_num}.mp3")
    else:
        log(f"Unknown file type: {file_type}", level="WARNING")
        return None

def prepare_chapter_directory(output_path):
    """
    Create chapter directory structure and return necessary paths.
    This function is used by TTS providers to organize output files.

    Args:
        output_path: Original output path for the audio file

    Returns:
        tuple: (chapter_dir, new_output_path, chapter_name)
    """
    # Create provider-specific directory structure
    provider_dir = os.path.dirname(output_path)
    
    # Extract properly padded name for consistent directory structure
    # Get the chapter number from the output path (e.g., chapter_01.mp3 -> 01)
    basename = os.path.basename(output_path)
    if basename.startswith("chapter_") and basename.endswith(".mp3"):
        # Ensure we use the padded number format (e.g., chapter_01, not chapter_1)
        chapter_num_str = basename[8:-4]  # Extract "01" from "chapter_01.mp3"
        # Keep the original padding
        chapter_name = f"chapter_{chapter_num_str}"
    else:
        # Fallback to simple basename without extension
        chapter_name = os.path.splitext(basename)[0]
        
    # Place chapter directory under the provider directory
    chapter_dir = os.path.join(provider_dir, chapter_name)
    os.makedirs(chapter_dir, exist_ok=True)

    # Update output path to be in the chapter directory
    new_output_path = os.path.join(chapter_dir, os.path.basename(output_path))

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(new_output_path), exist_ok=True)
    
    return chapter_dir, new_output_path, chapter_name

def get_best_string_match(query, candidates, key=None, threshold=0.5, debug=False):
    """
    Find the best matching string in a list using string similarity.

    Args:
        query (str): The string to match
        candidates (list or dict): List of strings or dictionaries to search through
        key (callable, optional): Function to extract string from each candidate if candidates are not strings
        threshold (float): Minimum similarity ratio to consider a match (0.0 to 1.0)
        debug (bool): Whether to output detailed debug logs regardless of log level

    Returns:
        tuple: (best_match, best_similarity, best_value) or (None, 0, None) if no match above threshold
    """
    # Always enable debug logging when debugging voice mappings
    if "voice" in str(query).lower() or debug:
        debug = True
        log(f"String matching debug for query: '{query}'", level="DEBUG")
        if isinstance(candidates, dict):
            log(f"Candidates (keys): {list(candidates.keys())}", level="DEBUG")
        else:
            log(f"Candidates count: {len(candidates)}", level="DEBUG")

    if not query or not candidates:
        if debug:
            log(f"Empty query or candidates list. Query: '{query}', Candidates empty: {not candidates}", level="DEBUG")
        return None, 0, None

    best_match = None
    best_similarity = 0
    best_value = None
    similarity_scores = []

    # Handle dictionary input correctly
    if isinstance(candidates, dict):
        items = candidates.items()
        if debug:
            log(f"Processing dictionary with keys: {list(candidates.keys())}", level="DEBUG")
    else:
        items = enumerate(candidates)
        if debug:
            log(f"Processing list with {len(candidates)} items", level="DEBUG")

    # Normalize query for comparison
    query_lower = query.lower()

    # Keep track of exact matches to prioritize them
    exact_matches = []

    for identifier, item in items:
        # When we're iterating through a dictionary, identifier is the key (character name)
        # and item is the value (voice mappings)
        if isinstance(candidates, dict):
            compare_string = identifier  # Use the key (character name) for comparison
        # Otherwise use the standard approach for lists
        elif key is not None:
            compare_string = key(item)
        elif isinstance(item, str):
            compare_string = item
        elif isinstance(item, dict) and "name" in item:
            compare_string = item["name"]
        else:
            # Skip items we can't extract a string from
            if debug:
                log(f"Could not extract string from item: {item}", level="DEBUG")
            continue

        # Skip empty strings
        if not compare_string:
            continue

        # First check for exact match (case-insensitive)
        if compare_string.lower() == query_lower:
            if debug:
                log(f"Exact match found: '{compare_string}' for query '{query}'", level="DEBUG")
            exact_matches.append((compare_string, 1.0, item))

        # Calculate similarity
        similarity = difflib.SequenceMatcher(None, compare_string.lower(), query_lower).ratio()

        if debug:
            similarity_scores.append((compare_string, similarity))

        # Check if this is the best match so far
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = compare_string
            best_value = item

    # Debug output all similarity scores
    if debug:
        # Sort by similarity score in descending order
        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        log(f"Top 5 similarity scores for '{query}':", level="DEBUG")
        for i, (name, score) in enumerate(similarity_scores[:5], 1):
            log(f"  {i}. '{name}': {score:.4f}", level="DEBUG")

        if best_similarity < threshold:
            log(f"Best match '{best_match}' with similarity {best_similarity:.4f} is below threshold {threshold}", level="DEBUG")

    # Prioritize exact matches if any
    if exact_matches:
        # Use the first exact match
        best_match, best_similarity, best_value = exact_matches[0]
        return best_match, best_similarity, best_value

    # Only return a match if it meets the threshold
    if best_similarity >= threshold:
        return best_match, best_similarity, best_value
    else:
        return None, 0, None

"""
Audio generation for Audible.

This module provides functionality for generating audio from TTS request files.
"""

import os
import json
import asyncio
from audible.utils.common import (
    log, extract_chapter_num, get_padded_chapter_num, get_chapter_filename
)
from audible.tts.tts_factory import TTSFactory
from audible.utils.thread_pool import process_batch_async

def process_tts_files(book_dir, provider=None, model=None, use_cloned_voices=False, force=False, single_file=None, use_async=False, multi_speaker=False):
    """
    Process TTS request files to generate audio.

    Args:
        book_dir (str): Directory containing the book data
        provider (str): TTS provider to use (openai, cartesia)
        model (str): TTS model to use (provider-specific)
        use_cloned_voices (bool): Whether to use cloned voices if available
        force (bool): Force regeneration of audio files even if they exist
        single_file (str): Optional specific TTS file to process
        use_async (bool): Whether to use asynchronous processing (default: True)
        multi_speaker (bool): Whether to use multi-speaker audio generation (Google TTS only)

    Returns:
        bool: True if successful, False otherwise
    """
    log(f"Generating audio for book in {book_dir}")

    # Create audio directory if it doesn't exist
    audio_dir = os.path.join(book_dir, "audio")
    if not os.path.exists(audio_dir):
        os.makedirs(audio_dir)
        log(f"Created audio directory at {audio_dir}")

    # Get TTS provider from environment or function parameter
    tts_provider = provider or os.getenv("AUDIBLE_TTS_PROVIDER", "openai").lower()
    tts_model = model or os.getenv("AUDIBLE_TTS_MODEL", None)
    use_cloned = use_cloned_voices or os.getenv("AUDIBLE_USE_CLONED_VOICES", "false").lower() == "true"

    # Check for TTS directory
    tts_dir = os.path.join(book_dir, "tts", tts_provider)
    if not os.path.exists(tts_dir):
        log(f"TTS directory not found at {tts_dir}. Run prepare_tts first.", level="ERROR")
        return False

    log(f"Using TTS provider: {tts_provider}")
    if tts_model:
        log(f"Using TTS model: {tts_model}")
    if use_cloned:
        log("Using cloned voices if available")

    # Create TTS engine
    tts_engine = TTSFactory.create(
        provider=tts_provider,
        model=tts_model,
        use_cloned_voices=use_cloned,
        multi_speaker=multi_speaker
    )

    # Get TTS request files to process
    if single_file:
        log(f"Processing single TTS file: {single_file}")

        # Convert any relative path to absolute using book_dir as base
        if not os.path.isabs(single_file):
            # First check if the file exists as provided
            if os.path.exists(single_file):
                tts_file_path = os.path.abspath(single_file)
            else:
                log(f"TTS file not found: {single_file}", level="ERROR")
                log(f"Tried: {single_file}")
                return False
        else:
            # Absolute path provided
            if os.path.exists(single_file):
                tts_file_path = single_file
            else:
                log(f"TTS file not found: {single_file}", level="ERROR")
                return False

        # Now we have a valid tts_file_path
        tts_dir = os.path.dirname(tts_file_path)
        tts_files = [os.path.basename(tts_file_path)]
        log(f"Using TTS file at {tts_file_path}")
    else:
        # Get all TTS files
        tts_files = sorted([f for f in os.listdir(tts_dir) if f.endswith("_tts.json")])

    if not tts_files:
        log(f"No TTS request files found in {tts_dir}", level="ERROR")
        return False

    log(f"Found {len(tts_files)} TTS request files to process")

    # Calculate padding digits based on total number of files
    num_chapters = len(tts_files)

    # Check if we can use async processing when requested
    if use_async:
        has_async = hasattr(tts_engine, 'generate_audio_from_request_async')
        if has_async:
            log(f"Using asynchronous processing for {len(tts_files)} TTS files as requested")
            # Process files using async/await pattern
            return run_async_processing(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force)
        else:
            log(f"Asynchronous processing requested but not supported by the {tts_provider} provider. Using synchronous processing instead.", level="WARNING")
            return run_sync_processing(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force)
    else:
        log(f"Using synchronous processing for {len(tts_files)} TTS files")
        # Process files sequentially
        return run_sync_processing(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force)

def run_sync_processing(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force):
    """Process TTS files synchronously."""
    # Process each TTS request file
    success_count = 0
    for tts_filename in tts_files:
        # Extract chapter number from the TTS filename
        chapter_num_match = tts_filename.split("_")
        if len(chapter_num_match) >= 2 and "chapter" in tts_filename:
            try:
                # Try to extract the number from format "chapter_XX_tts.json"
                chapter_num = int(chapter_num_match[1])
            except (ValueError, IndexError):
                log(f"Could not extract chapter number from TTS filename: {tts_filename}", level="ERROR")
                continue
        else:
            log(f"Unexpected TTS filename format: {tts_filename}", level="ERROR")
            continue

        tts_file_path = os.path.join(tts_dir, tts_filename)

        # Load TTS request
        with open(tts_file_path, "r", encoding="utf-8") as f:
            tts_request = json.load(f)

        # Get output audio file path using the utility function
        audio_path = get_chapter_filename(
            book_dir, chapter_num, 'audio', num_chapters=num_chapters,
        )

        # Skip if audio file exists and we're not forcing regeneration
        if os.path.exists(audio_path) and not force:
            log(f"Audio file for chapter {chapter_num} already exists at {audio_path}. Use --force to regenerate.")
            continue

        log(f"Generating audio for chapter {chapter_num}")

        # Generate audio
        success = tts_engine.generate_audio_from_request(tts_request, audio_path)

        if success:
            log(f"Generated audio for chapter {chapter_num} at {audio_path}")
            chapter_dir = os.path.join(os.path.dirname(audio_path), os.path.splitext(os.path.basename(audio_path))[0])
            log(f"All segment files are preserved in the chapter directory: {chapter_dir}/")
            success_count += 1

            # Update TTS request with status
            tts_request["status"] = "processed"
            with open(tts_file_path, "w", encoding="utf-8") as f:
                json.dump(tts_request, f, indent=2)
        else:
            log(f"Failed to generate audio for chapter {chapter_num}", level="ERROR")

    log(f"Audio generation complete. Successfully processed {success_count} out of {len(tts_files)} files.")
    return success_count > 0

def run_async_processing(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force):
    """Process TTS files asynchronously."""
    # Create event loop if necessary
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the async processing
    return loop.run_until_complete(
        process_files_async(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force)
    )

async def process_files_async(tts_engine, tts_dir, tts_files, book_dir, num_chapters, force):
    """Async function to process multiple TTS files concurrently."""
    # Prepare processing tasks
    tasks_to_process = []

    for tts_filename in tts_files:
        # Extract chapter number from the TTS filename
        chapter_num_match = tts_filename.split("_")
        if len(chapter_num_match) >= 2 and "chapter" in tts_filename:
            try:
                # Try to extract the number from format "chapter_XX_tts.json"
                chapter_num = int(chapter_num_match[1])
            except (ValueError, IndexError):
                log(f"Could not extract chapter number from TTS filename: {tts_filename}", level="ERROR")
                continue
        else:
            log(f"Unexpected TTS filename format: {tts_filename}", level="ERROR")
            continue

        tts_file_path = os.path.join(tts_dir, tts_filename)

        # Load TTS request
        try:
            with open(tts_file_path, "r", encoding="utf-8") as f:
                tts_request = json.load(f)
        except Exception as e:
            log(f"Error loading TTS request file {tts_filename}: {e}", level="ERROR")
            continue

        # Get output audio file path using the utility function
        audio_path = get_chapter_filename(
            book_dir, chapter_num, 'audio', num_chapters=num_chapters
        )

        # Skip if audio file exists and we're not forcing regeneration
        if os.path.exists(audio_path) and not force:
            log(f"Audio file for chapter {chapter_num} already exists at {audio_path}. Use --force to regenerate.")
            continue

        # Add to list of files to process
        tasks_to_process.append({
            'chapter_num': chapter_num,
            'tts_file_path': tts_file_path,
            'tts_request': tts_request,
            'audio_path': audio_path
        })

    if not tasks_to_process:
        log("No TTS files need processing")
        return True

    log(f"Processing {len(tasks_to_process)} TTS files in parallel")

    # Set maximum concurrent tasks (process up to 5 chapters at a time)
    max_concurrent = min(5, len(tasks_to_process))
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_file_with_semaphore(task):
        """Process a single TTS file with semaphore to limit concurrency."""
        async with semaphore:
            return await process_single_file_async(tts_engine, task)

    # Create tasks for all files
    coroutines = [process_file_with_semaphore(task) for task in tasks_to_process]

    # Execute all tasks concurrently and gather results
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    # Count successful files
    success_count = sum(1 for result in results if result is True)

    log(f"Audio generation complete. Successfully processed {success_count} out of {len(tasks_to_process)} files.")
    return success_count > 0

async def process_single_file_async(tts_engine, task):
    """Process a single TTS file asynchronously."""
    chapter_num = task['chapter_num']
    tts_file_path = task['tts_file_path']
    tts_request = task['tts_request']
    audio_path = task['audio_path']

    try:
        log(f"Generating audio for chapter {chapter_num}")

        # Generate audio asynchronously
        success = await tts_engine.generate_audio_from_request_async(tts_request, audio_path)

        if success:
            log(f"Generated audio for chapter {chapter_num} at {audio_path}")
            chapter_dir = os.path.join(os.path.dirname(audio_path), os.path.splitext(os.path.basename(audio_path))[0])
            log(f"All segment files are preserved in the chapter directory: {chapter_dir}/")

            # Update TTS request with status
            tts_request["status"] = "processed"
            with open(tts_file_path, "w", encoding="utf-8") as f:
                json.dump(tts_request, f, indent=2)

            return True
        else:
            log(f"Failed to generate audio for chapter {chapter_num}", level="ERROR")
            return False
    except Exception as e:
        log(f"Error processing chapter {chapter_num}: {e}", level="ERROR")
        return False
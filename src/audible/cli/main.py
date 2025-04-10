"""
Main CLI for the Audible package.
"""

import os
import sys
import argparse
from audible.utils.common import log
from audible.core.audio_generator import process_tts_files
from audible.core.character_extractor import extract_characters
from audible.core.chapter_analyzer import analyze_chapters
from audible.core.script_generator import generate_scripts
from audible.core.tts_preparer import prepare_tts, prepare_voice_mappings
from audible.core.book_preparer import prepare_book
from audible.cartesia import (
    list_voices,
    clone_voices,
    generate_voice_samples,
    download_voice_sample
)

def cartesia_subcommand(args):
    """Handle cartesia-related subcommands."""
    if args.command == 'list-voices':
        list_voices(
            gender=args.gender,
            limit=args.limit if hasattr(args, 'limit') else 100,
            is_owner=args.is_owner if hasattr(args, 'is_owner') else False,
            is_starred=args.is_starred if hasattr(args, 'is_starred') else False,
            search=args.search if hasattr(args, 'search') else None,
            output=args.output if hasattr(args, 'output') else None
        )
    elif args.command == 'clone-voice':
        clone_voices(
            book_dir=args.book_dir,
            character=args.character,
            voice_clone_dir=args.voice_clone_dir,
            wait_for_completion=not args.no_wait,
            create_backup=not args.no_backup
        )
    elif args.command == 'generate-samples':
        generate_voice_samples(
            book_dir=args.book_dir,
            output_dir=args.output_dir,
            use_openai=not args.cartesia_only,
            use_cartesia=not args.openai_only,
            sample_text=args.sample_text,
            force=args.force,
            character=args.character
        )
    elif args.command == 'download-sample':
        download_voice_sample(
            youtube_url=args.url,
            character_name=args.character,
            book_dir=args.book_dir,
            start_time=args.start,
            end_time=args.end,
            audio_format=args.format,
            match_case=args.match_case
        )
    else:
        log(f"Unknown cartesia command: {args.command}")
        sys.exit(1)

def main():
    """Main entry point for the Audible CLI."""
    parser = argparse.ArgumentParser(description="Audible CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommands")

    # Main command arguments
    parser.add_argument("--book-dir", help="Directory containing the book data")
    parser.add_argument("--tts-provider", help="TTS provider to use (openai, cartesia, google, csm)", default="openai")
    parser.add_argument("--tts-model", help="TTS model to use (provider-specific)", default=None)
    parser.add_argument("--use-cloned-voices", help="Use cloned voices if available", action="store_true")
    parser.add_argument("--no-emotions", help="Disable emotion-based voice modulation", action="store_true")
    parser.add_argument("--llm-provider", help="LLM provider to use (openai, anthropic)", default="openai")
    parser.add_argument("--llm-model", help="LLM model to use (provider-specific)")
    parser.add_argument("--prepare-book", help="Split book.txt into chapters", action="store_true")
    parser.add_argument("--extract-characters", help="Only extract character information", action="store_true")
    parser.add_argument("--analyze-chapters", help="Only analyze chapter interactions", action="store_true")
    parser.add_argument("--generate-scripts", help="Only generate scripts", action="store_true")
    parser.add_argument("--prepare-voices", help="Create voice_mappings.json for all characters", action="store_true")
    parser.add_argument("--prepare-tts", help="Only prepare TTS request files", action="store_true")
    parser.add_argument("--generate-audio", help="Only generate audio from TTS files", action="store_true")
    parser.add_argument("--tts-file", help="Process a single TTS file")
    parser.add_argument("--force", help="Force regeneration of files", action="store_true")
    parser.add_argument("--no-async", dest="no_async", help="Disable asynchronous processing", action="store_true")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       default="INFO", help="Set the logging level")

    # Cartesia subcommand
    cartesia_parser = subparsers.add_parser('cartesia', help='Cartesia TTS tools')
    cartesia_subparsers = cartesia_parser.add_subparsers(dest="command", help="Cartesia commands")

    # List voices command
    list_parser = cartesia_subparsers.add_parser('list-voices', help='List available Cartesia voices')
    list_parser.add_argument('--gender', help='Filter by gender (masculine/feminine/gender_neutral)',
                          choices=['masculine', 'feminine', 'gender_neutral'])
    list_parser.add_argument('--limit', type=int, default=100, help='Number of voices to return (1-100)')
    list_parser.add_argument('--is-owner', action='store_true', help='Only return voices owned by the current user')
    list_parser.add_argument('--is-starred', action='store_true', help='Only return starred voices')
    list_parser.add_argument('--output', help='Path to save voice information as JSON')
    list_parser.add_argument('--search', type=str, default=None,
                       help='Search for voices with specific terms (comma-separated)')

    # Clone voice command
    clone_parser = cartesia_subparsers.add_parser('clone-voice', help='Clone a voice using a sample')
    clone_parser.add_argument('--book-dir', required=True, help='Directory containing the book data')
    clone_parser.add_argument('--character', help='Only clone voice for a specific character')
    clone_parser.add_argument('--voice-clone-dir', help='Directory containing voice samples to clone')
    clone_parser.add_argument('--no-wait', action='store_true', help='Do not wait for voice cloning jobs to complete')
    clone_parser.add_argument('--no-backup', action='store_true', help='Do not create a backup of the original voice_mappings.json')

    # Generate samples command
    sample_parser = cartesia_subparsers.add_parser('generate-samples', help='Generate voice samples')
    sample_parser.add_argument('--book-dir', default='.', help='Directory containing the voice_mappings.json file')
    sample_parser.add_argument('--output-dir', help='Directory to save voice samples')
    sample_parser.add_argument('--openai-only', action='store_true', help='Generate only OpenAI voice samples')
    sample_parser.add_argument('--cartesia-only', action='store_true', help='Generate only Cartesia voice samples')
    sample_parser.add_argument('--sample-text', help='Custom sample text to use instead of default')
    sample_parser.add_argument('--force', action='store_true', help='Force regeneration of existing samples')
    sample_parser.add_argument('--character', help='Generate sample for a specific character only')

    # Download voice sample command
    download_parser = cartesia_subparsers.add_parser('download-sample', help='Download a voice sample from YouTube')
    download_parser.add_argument('--url', required=True, help='YouTube URL to download audio from')
    download_parser.add_argument('--character', required=True, help='Character name for the voice sample')
    download_parser.add_argument('--book-dir', default='.', help='Directory containing the book data')
    download_parser.add_argument('--start', help='Start time for audio clip (format: MM:SS or HH:MM:SS)')
    download_parser.add_argument('--end', help='End time for audio clip (format: MM:SS or HH:MM:SS)')
    download_parser.add_argument('--format', choices=['mp3', 'wav', 'm4a'], default='mp3', help='Audio format for the output file')
    download_parser.add_argument('--match-case', action='store_true', help='Match character name case in voice_mappings.json')

    args = parser.parse_args()

    # Set the log level environment variable
    os.environ["AUDIBLE_LOG_LEVEL"] = args.log_level

    # Handle cartesia subcommand
    if args.subcommand == 'cartesia':
        # If no specific cartesia command was given, print help for the cartesia subcommand
        if args.command is None:
            cartesia_parser.print_help()
            sys.exit(0)
        else:
            cartesia_subcommand(args)
            return

    # Ensure book_dir is provided for main commands
    if not args.book_dir and args.subcommand is None:
        parser.error("--book-dir is required unless using a subcommand")

    # Set environment variables for LLM provider and model
    if args.llm_provider:
        os.environ["AUDIBLE_LLM_PROVIDER"] = args.llm_provider
    if args.llm_model:
        os.environ["AUDIBLE_LLM_MODEL"] = args.llm_model

    # Set environment variable for async processing (enabled by default)
    if args.no_async:
        os.environ["AUDIBLE_USE_ASYNC"] = "false"
        log("Asynchronous processing disabled")
    else:
        os.environ["AUDIBLE_USE_ASYNC"] = "true"
        log("Using asynchronous processing (default)")

    # Set environment variables for TTS provider and model
    if args.tts_provider:
        os.environ["AUDIBLE_TTS_PROVIDER"] = args.tts_provider
    if args.tts_model:
        os.environ["AUDIBLE_TTS_MODEL"] = args.tts_model

    # Print configuration
    log(f"Using LLM provider: {args.llm_provider}")
    if args.llm_model:
        log(f"Using LLM model: {args.llm_model}")

    log(f"Using TTS provider: {args.tts_provider}")
    if args.tts_model:
        log(f"Using TTS model: {args.tts_model}")

    # Process book based on the requested operations
    if args.prepare_book:
        prepare_book(book_dir=args.book_dir, force=args.force)

    if args.analyze_chapters:
        analyze_chapters(book_dir=args.book_dir, force=args.force)

    if args.extract_characters:
        extract_characters(book_dir=args.book_dir, force=args.force)

    if args.prepare_voices:
        prepare_voice_mappings(book_dir=args.book_dir, force=args.force)

    if args.generate_scripts:
        generate_scripts(book_dir=args.book_dir, force=args.force)

    if args.prepare_tts:
        prepare_tts(book_dir=args.book_dir, force=args.force, provider=args.tts_provider)

    if args.generate_audio or args.tts_file:
        log("Generating audio from TTS files")
        process_tts_files(
            book_dir=args.book_dir,
            provider=args.tts_provider,
            model=args.tts_model,
            use_cloned_voices=args.use_cloned_voices,
            force=args.force,
            single_file=args.tts_file,
            use_async=not args.no_async
        )
        return

    # If no specific task was requested, show a message
    if not any([args.prepare_book, args.extract_characters, args.analyze_chapters,
                args.generate_scripts, args.prepare_tts, args.generate_audio,
                args.tts_file]):
        log("No specific task requested. Use --help to see available options.")
        sys.exit(1)

if __name__ == "__main__":
    main()
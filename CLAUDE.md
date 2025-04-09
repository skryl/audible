# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- **Setup:** `pip install -e .` (install in develop mode)
- **Run:** `python audible.py --book-dir <book_dir>` 
- **Run steps individually:**
  - `python audible.py --book-dir <book_dir> --extract-characters`
  - `python audible.py --book-dir <book_dir> --analyze-chapters`
  - `python audible.py --book-dir <book_dir> --generate-scripts`
  - `python audible.py --book-dir <book_dir> --prepare-tts`
  - `python audible.py --book-dir <book_dir> --generate-audio`

## Code Style

- **Imports:** Group standard library first, then third-party, then local imports
- **Type Hints:** Use type annotations for function parameters and return values
- **Docstrings:** Use Google-style docstrings with Args/Returns sections
- **Error Handling:** Use try/except with specific exception types and logging
- **Naming:** snake_case for variables/functions, PascalCase for classes
- **Async/Await:** Support both synchronous and asynchronous operation when possible
- **Environment Variables:** Use os.getenv with defaults for configuration
- **Logging:** Use common.log() function for consistent output formatting
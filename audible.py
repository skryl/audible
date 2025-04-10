#!/usr/bin/env python
"""
Python script to run the audible CLI main function directly.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
if os.path.exists('.env'):
    print("Loading environment variables from .env file")
    load_dotenv()
    # Check if loaded properly
    if 'OPENAI_API_KEY' in os.environ:
        print(f"OPENAI_API_KEY loaded: {os.environ['OPENAI_API_KEY'][:5]}...{os.environ['OPENAI_API_KEY'][-5:]}")
    else:
        print("WARNING: OPENAI_API_KEY not found in environment after loading .env")
else:
    print("WARNING: .env file not found")

# Add src directory to Python path for imports
src_dir = os.path.join(os.path.dirname(__file__), "src")
sys.path.insert(0, src_dir)

# Import CLI main function
from audible.cli.main import main as cli_main

def main():
    cli_main()

if __name__ == "__main__":
    # Call the CLI main function directly
    main()
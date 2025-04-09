#!/bin/bash
# Simple script to run all audible book generation steps sequentially

# Load environment variables from .env file properly
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    set -a  # automatically export all variables
    source .env
    set +a
else
    echo "Error: .env file not found"
    exit 1
fi

# Verify API keys were loaded
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not loaded from .env file"
    exit 1
fi

# Get book directory from first argument
if [ -z "$1" ]; then
  echo "Usage: $0 <book_directory> [--use-cloned-voices]"
  exit 1
fi

BOOK_DIR=$1
shift

# Check for cloned voices flag
CLONED_VOICES_FLAG=""
if [ "$1" = "--use-cloned-voices" ]; then
  CLONED_VOICES_FLAG="--use-cloned-voices"
fi

# Set model and provider variables
LLM_PROVIDER="--llm-provider openai"
LLM_MODEL="--llm-model o3-mini"
TTS_PROVIDER="--tts-provider openai"
TTS_MODEL="--tts-model gpt-4o-mini-tts"
LOG_LEVEL="--log-level INFO"  # Change to DEBUG for more detailed logs

echo "==== Running complete audiobook pipeline on $BOOK_DIR with API keys ===="
echo "Using OpenAI API key: ${OPENAI_API_KEY:0:5}...${OPENAI_API_KEY: -5}"
echo "Using LLM Provider: openai with model: o3-mini"
echo "Using TTS Provider: openai with model: gpt-4o-mini-tts"

echo "Step 1: Preparing book"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --prepare-book --force || exit 1

echo "Step 2: Analyzing chapters"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --analyze-chapters --force || exit 1

echo "Step 3: Extracting characters"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --extract-characters --force || exit 1

echo "Step 4: Generating scripts"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --generate-scripts --force || exit 1

echo "Step 5: Preparing TTS requests"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --prepare-tts --force || exit 1

echo "Step 6: Generating audio"
./audible.py --book-dir $BOOK_DIR $LLM_PROVIDER $LLM_MODEL $TTS_PROVIDER $TTS_MODEL $CLONED_VOICES_FLAG $LOG_LEVEL --generate-audio --force || exit 1

echo "==== Audiobook generation complete! ===="
echo "Output files are in the $BOOK_DIR directory"
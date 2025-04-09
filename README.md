# Audible - AI Audiobook Generator

A Python package for generating AI-powered audiobooks from text using language models for character analysis and text-to-speech providers for audio generation. The library supports multiple TTS providers (OpenAI, Cartesia, Google) and multiple LLM providers (OpenAI, Anthropic, Google).

## Features

- Extract and analyze characters from book text
- Analyze character interactions in each chapter
- Generate character profiles with personalities, appearances, and voice traits
- Generate speech scripts with dialogue and narration segments
- Convert text to speech using multiple TTS providers:
  - OpenAI TTS (voices: alloy, echo, fable, onyx, nova, shimmer)
  - Cartesia TTS (with voice cloning support)
  - Google Cloud TTS
- Stitch audio segments together into complete chapters
- Support for voice cloning and custom voices
- Asynchronous processing for faster audio generation

## Installation

### From PyPI (Recommended)

```bash
pip install audible
```

### From Source

```bash
git clone https://github.com/yourusername/audible.git
cd audible
pip install -e .
```

## Quick Start

1. Create a directory with your book in a file called `book.txt`

```bash
mkdir -p my_book
cp your_book.txt my_book/book.txt
```

2. Set up your API keys as environment variables:

```bash
# Choose one or more of these providers:
export OPENAI_API_KEY='your-openai-api-key'
export ANTHROPIC_API_KEY='your-anthropic-api-key'
export CARTESIA_API_KEY='your-cartesia-api-key'
# For Google, you need a service account credentials file:
export GOOGLE_APPLICATION_CREDENTIALS='path/to/credentials.json'
```

3. Run the full audiobook generation pipeline:

```bash
audible --book-dir my_book
```

4. Find the generated audiobook in `my_book/audio/`

## Requirements

- Python 3.8+
- FFmpeg (for audio processing)
- API keys for at least one of:
  - OpenAI API key (for LLM and TTS)
  - Anthropic API key (for LLM)
  - Cartesia API key (for TTS)
  - Google Cloud credentials (for LLM and TTS)

## Detailed Usage

### Command Line Arguments

```
usage: audible [-h] [--book-dir BOOK_DIR] [--tts-provider TTS_PROVIDER]
               [--tts-model TTS_MODEL] [--use-cloned-voices] [--no-emotions]
               [--llm-provider LLM_PROVIDER] [--llm-model LLM_MODEL]
               [--prepare-book] [--extract-characters] [--analyze-chapters]
               [--generate-scripts] [--prepare-tts] [--generate-audio]
               [--tts-file TTS_FILE] [--force] [--async]
               [--log-level {DEBUG,INFO,WARNING,ERROR}]
               {cartesia} ...

Audible CLI

positional arguments:
  {cartesia}            Subcommands
    cartesia            Cartesia TTS tools

options:
  -h, --help            show this help message and exit
  --book-dir BOOK_DIR   Directory containing the book data
  --tts-provider TTS_PROVIDER
                        TTS provider to use (openai, cartesia, google)
  --tts-model TTS_MODEL
                        TTS model to use (provider-specific)
  --use-cloned-voices   Use cloned voices if available
  --no-emotions         Disable emotion-based voice modulation
  --llm-provider LLM_PROVIDER
                        LLM provider to use (openai, anthropic, google)
  --llm-model LLM_MODEL
                        LLM model to use (provider-specific)
  --prepare-book        Split book.txt into chapters
  --extract-characters  Only extract character information
  --analyze-chapters    Only analyze chapter interactions
  --generate-scripts    Only generate scripts
  --prepare-tts         Only prepare TTS request files
  --generate-audio      Only generate audio from TTS files
  --tts-file TTS_FILE   Process a single TTS file
  --force               Force regeneration of files
  --async               Use asynchronous processing if available
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Set the logging level
```

### Complete Audiobook Generation Workflow

The typical workflow consists of these sequential steps:

1. **Prepare Book**: Split the book.txt file into individual chapter files
2. **Analyze Chapters**: Analyze character interactions and relationships in each chapter
3. **Extract Characters**: Analyze the text to identify characters and create profiles
4. **Generate Scripts**: Convert raw text into structured scripts with dialogue and narration
5. **Prepare Voices**: Create voice mappings for all characters
6. **Prepare TTS**: Create TTS request files for each chapter with voice assignments
7. **Generate Audio**: Convert text to speech and combine into chapter audio files

You can run the entire process with a single command:

```bash
audible --book-dir my_book
```

Or run individual steps as needed:

```bash
# First time setup:
audible --book-dir my_book --prepare-book
audible --book-dir my_book --analyze-chapters
audible --book-dir my_book --extract-characters

# Generate scripts:
audible --book-dir my_book --generate-scripts

# Generate audio:
audible --book-dir my_book --prepare-voices
audible --book-dir my_book --prepare-tts
audible --book-dir my_book --generate-audio
```

### Detailed Steps Description

#### Step 1: Prepare Book

The `prepare-book` command processes the initial book.txt file and splits it into individual chapter files for further processing:

```bash
audible --book-dir my_book --prepare-book
```

This command:
1. Looks for a `book.txt` file in the specified directory
2. Identifies chapter breaks based on common chapter heading patterns
3. Creates a `chapters` directory if it doesn't exist
4. Splits the book into individual chapter files (chapter_001.txt, chapter_002.txt, etc.)
5. Creates a `chapters.json` file with metadata about each chapter

You can regenerate the chapters by adding the `--force` flag.

#### Step 2: Analyze Chapters

The `analyze-chapters` command examines each chapter to identify character interactions and speech patterns:

```bash
audible --book-dir my_book --analyze-chapters
```

This command:
1. Processes each chapter file in the `chapters` directory
2. Creates an `analysis` directory if it doesn't exist
3. Identifies dialogue, speakers, and interaction patterns
4. Saves analysis data for each chapter in JSON format
5. Uses AI to enhance the accuracy of dialogue attribution

This step is crucial for properly attributing dialogue to characters in the next steps.

#### Step 3: Extract Characters

The `extract-characters` command builds a comprehensive list of characters from the book:

```bash
audible --book-dir my_book --extract-characters
```

This command:
1. Creates a `characters` directory if it doesn't exist
2. Analyzes all chapter data to identify unique characters
3. Uses AI to determine character attributes (gender, importance, etc.)
4. Creates a `characters.json` file with detailed character information
5. Helps distinguish between major and minor characters

This step provides essential information for voice assignment and script generation.

#### Step 4: Generate Scripts

The `generate-scripts` command converts raw chapter text into structured scripts with dialogue and narration:

```bash
audible --book-dir my_book --generate-scripts
```

This command:
1. Creates a `scripts` directory if it doesn't exist
2. Processes each chapter using the character and analysis data
3. Converts raw text into a structured script format
4. Properly attributes dialogue to characters
5. Separates narration from character speech
6. Saves each chapter as a structured script file

The scripts are formatted to clearly indicate which character is speaking and separate narration from dialogue.

#### Step 5: Prepare Voices

The `prepare-voices` command creates voice mappings for all characters:

```bash
audible --book-dir my_book --prepare-voices
```

This command:
1. Creates a `voices` directory if it doesn't exist
2. Reads character data from `characters.json` (must run `extract-characters` first)
3. Creates a `voice_mappings.json` file with default voice assignments for all characters
4. Assigns appropriate voices based on character gender when available
5. Includes default voices for both OpenAI and Cartesia TTS providers

You can regenerate the voice mappings file by adding the `--force` flag:

```bash
audible --book-dir my_book --prepare-voices --force
```

#### Step 6: Prepare TTS

The `prepare-tts` command creates TTS (Text-to-Speech) request files for each script:

```bash
audible --book-dir my_book --prepare-tts
```

This command:
1. Creates a `tts` directory if it doesn't exist
2. Reads the script files from the `scripts` directory
3. Uses the `voice_mappings.json` to assign voices to characters
4. Creates TTS request files formatted for the specified provider (OpenAI, Cartesia, etc.)
5. Optimizes text chunking for the TTS provider's limitations

You can specify a different TTS provider using the `--tts-provider` option:

```bash
audible --book-dir my_book --prepare-tts --tts-provider openai
```

#### Step 7: Generate Audio

The `generate-audio` command processes the TTS request files and creates audio files:

```bash
audible --book-dir my_book --generate-audio
```

This command:
1. Creates an `audio` directory if it doesn't exist
2. Processes each TTS request file using the specified provider's API
3. Generates audio files for each text segment
4. Combines the segments into complete chapter audio files
5. Applies any necessary audio processing (normalization, timing adjustments, etc.)

You can process a single TTS file using the `--tts-file` option:

```bash
audible --book-dir my_book --generate-audio --tts-file chapter_001.json
```

### Voice Mappings

The system needs to assign specific voices to each character for text-to-speech conversion. You can generate default voice mappings using the `prepare-voices` command:

```bash
audible --book-dir my_book --prepare-voices
```

This command:
1. Creates a `voices` directory if it doesn't exist
2. Reads character data from `characters.json` (must run `extract-characters` first)
3. Creates a `voice_mappings.json` file with default voice assignments for all characters
4. Assigns appropriate voices based on character gender when available
5. Includes default voices for both OpenAI and Cartesia TTS providers

You can regenerate the voice mappings file by adding the `--force` flag:

```bash
audible --book-dir my_book --prepare-voices --force
```

After generating the default voice mappings, you can customize them by editing the `voice_mappings.json` file in the `voices` directory:

```json
{
  "Narrator": {
    "openai": "onyx",
    "cartesia": "0123456789abcdef0123456789abcdef",
    "google": "en-US-Neural2-D"
  },
  "Character Name": {
    "openai": "nova",
    "cartesia": "fedcba9876543210fedcba9876543210",
    "google": "en-US-Neural2-F"
  }
}
```

### Using Different TTS Providers

The package supports multiple TTS providers:

#### OpenAI TTS (Default)

```bash
audible --book-dir my_book --tts-provider openai
```

Available voices: alloy, echo, fable, onyx, nova, shimmer

#### Cartesia TTS

```bash
audible --book-dir my_book --tts-provider cartesia --tts-model "sonic-2"
```

##### Listing Available Cartesia Voices

You can explore available Cartesia voices with the list-voices command:

```bash
# List all available Cartesia voices
audible cartesia list-voices

# Filter voices by gender (masculine/feminine/gender_neutral)
audible cartesia list-voices --gender feminine

# Limit the number of results (default is 100)
audible cartesia list-voices --limit 20

# Search for voices by keywords in name or description
audible cartesia list-voices --search "british,calm"

# Filter by voice ownership or starred status
audible cartesia list-voices --is-owner
audible cartesia list-voices --is-starred

# Save voice information to a JSON file
audible cartesia list-voices --output voices.json
```

Cartesia supports voice cloning for characters:

```bash
# First, download voice samples:
audible cartesia download-sample --url "https://youtube.com/watch?v=example" --character "Character Name" --book-dir my_book --start "00:10" --end "00:40"

# Then clone voices:
audible cartesia clone-voice --book-dir my_book

# Use cloned voices:
audible --book-dir my_book --tts-provider cartesia --use-cloned-voices --generate-audio
```

#### Google Cloud TTS

```bash
audible --book-dir my_book --tts-provider google --tts-model "en-US-Neural2-F"
```

Requires setting up a Google Cloud service account and credentials.

### Provider-Specific Directories

By default, audio files are organized into provider-specific subdirectories:

```
my_book/
├── audio/
│   ├── openai/
│   │   ├── chapter_01/
│   │   │   ├── chapter_01.mp3          # Combined chapter audio
│   │   │   ├── chapter_01.list         # FFmpeg file list
│   │   │   ├── segment_0000.mp3        # Individual segment files
│   │   │   ├── segment_0001.mp3
│   │   │   └── ...
│   ├── cartesia/
│   │   ├── chapter_01/
│   │   └── ...
│   └── google/
│       ├── chapter_01/
│       └── ...
└── tts/
    ├── openai/
    │   ├── chapter_01_tts.json
    │   └── ...
    ├── cartesia/
    │   ├── chapter_01_tts.json
    │   └── ...
    └── google/
        ├── chapter_01_tts.json
        └── ...
```

### Using Different LLM Providers

Choose your LLM provider for text analysis and script generation:

```bash
# OpenAI:
audible --book-dir my_book --llm-provider openai --llm-model "gpt-4o"

# Anthropic:
audible --book-dir my_book --llm-provider anthropic --llm-model "claude-3-opus-20240229"

# Google:
audible --book-dir my_book --llm-provider google --llm-model "gemini-1.5-pro"
```

### Asynchronous Processing

Enable asynchronous processing for faster audio generation:

```bash
audible --book-dir my_book --generate-audio --async
```

### Logging Levels

Control the verbosity of output messages:

```bash
audible --book-dir my_book --log-level DEBUG
audible --book-dir my_book --log-level INFO
audible --book-dir my_book --log-level WARNING
audible --book-dir my_book --log-level ERROR
```

## Development

To work with the project locally without installing via pip:

1. Clone the repository:

```bash
git clone https://github.com/yourusername/audible.git
cd audible
```

2. Set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install the package in development mode:

```bash
pip install -e .
```

5. Run the script directly:

```bash
# Using the installed CLI:
audible --book-dir my_book

# Or run the module directly:
python -m audible.cli.main --book-dir my_book

# Or use the Python file:
python src/audible/cli/main.py --book-dir my_book

# Or use the shell script:
./audible.sh --book-dir my_book
```

### Project Structure

```
audible/
├── src/
│   └── audible/             # Main package
│       ├── __init__.py      # Package initialization
│       ├── cartesia/        # Cartesia TTS integration
│       ├── cli/             # Command-line interface
│       ├── core/            # Core functionality
│       │   ├── ai.py                # AI utilities
│       │   ├── audio.py             # Audio processing
│       │   ├── audio_generator.py   # Audio generation from TTS files
│       │   ├── book_preparer.py     # Book text preparation
│       │   ├── chapter_analyzer.py  # Chapter analysis
│       │   ├── character_extractor.py # Character identification
│       │   ├── formatters.py        # Text formatting utilities
│       │   ├── script_generator.py  # Script generation
│       │   ├── text_processing.py   # Text processing utilities
│       │   └── tts_preparer.py      # TTS request preparation
│       ├── llm/             # LLM provider integrations
│       │   ├── anthropic_llm.py     # Anthropic Claude integration
│       │   ├── google_llm.py        # Google Gemini integration
│       │   ├── llm_factory.py       # LLM provider factory
│       │   └── openai_llm.py        # OpenAI integration
│       ├── tts/             # TTS provider integrations
│       │   ├── cartesia_tts.py      # Cartesia TTS integration
│       │   ├── google_tts.py        # Google Cloud TTS integration
│       │   ├── openai_tts.py        # OpenAI TTS integration
│       │   └── tts_factory.py       # TTS provider factory
│       └── utils/           # Utility functions
│           ├── common.py            # Common utilities
│           └── thread_pool.py       # Threading utilities
├── tests/                  # Unit tests
├── audible.py              # Entry point script
├── audible.sh              # Shell script wrapper
├── setup.py                # Package setup
└── requirements.txt        # Dependencies
```

### Environment Variables

You can configure the system using environment variables:

```bash
# LLM configuration
export AUDIBLE_LLM_PROVIDER=openai  # or anthropic, google
export AUDIBLE_LLM_MODEL=gpt-4o     # model name

# TTS configuration
export AUDIBLE_TTS_PROVIDER=openai  # or cartesia, google
export AUDIBLE_TTS_MODEL=gpt-4o-mini-tts  # model name
export AUDIBLE_USE_CLONED_VOICES=true  # use cloned voices if available
export AUDIBLE_NO_EMOTIONS=false  # disable emotion-based voice modulation

# Logging
export AUDIBLE_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Processing
export AUDIBLE_USE_ASYNC=true  # use asynchronous processing
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
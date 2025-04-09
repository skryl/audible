import os
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.audio_generator import process_tts_files

# Mark tests in this file as asyncio
pytestmark = pytest.mark.asyncio

async def test_generate_audio_cartesia(temp_test_book_dir, mock_ffmpeg, mocker):
    """Test the audio generation step using mocked Cartesia TTS."""
    book_dir = temp_test_book_dir
    tts_provider = "cartesia" # Use a valid provider name for testing
    tts_output_dir = os.path.join(book_dir, "tts", tts_provider)
    llm_output_dir = os.path.join(book_dir, "llm")

    # --- Setup: Create directory structure ---
    os.makedirs(tts_output_dir, exist_ok=True)
    os.makedirs(llm_output_dir, exist_ok=True)
    audio_dir = os.path.join(book_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    
    # Create chapters directory with a dummy file
    chapters_dir = os.path.join(book_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    with open(os.path.join(chapters_dir, "01_Chapter 1.txt"), "w") as f:
        f.write("Dummy chapter content")
    
    # Create dummy TTS request file
    dummy_request_content = {
      "chapter_number": 1,
      "title": "Chapter 1: The Beginning",
      "audio_file": "chapter_01.mp3",
      "status": "pending",
      "segments": [
        {
            "type": "narration", 
            "text": "Segment 1 text.", 
            "speaker": "Narrator", 
            "emotion": "neutral", 
            "voice_traits": "calm",
            "voice_id": "cart-narrator-id"
        },
        {
            "type": "dialogue", 
            "text": "Segment 2 text.", 
            "speaker": "Alice", 
            "emotion": "happy", 
            "voice_traits": "cheerful",
            "voice_id": "cart-alice-id"
        },
        {
            "type": "dialogue", 
            "text": "Segment 3 text.", 
            "speaker": "Bob", 
            "emotion": "neutral", 
            "voice_traits": "plain",
            "voice_id": "cart-bob-id"
        }
      ]
    }
    
    # Write to the root TTS directory with the correct pattern
    tts_dir = os.path.join(book_dir, "tts")
    request_file_path = os.path.join(tts_dir, "chapter_01_tts.json")
    with open(request_file_path, 'w') as f:
        import json
        json.dump(dummy_request_content, f)
    
    # Create chapter directory and dummy segment files
    chapter_output_dir = os.path.join(tts_output_dir, "chapter_01")
    os.makedirs(chapter_output_dir, exist_ok=True)
    
    segment_names = ["segment_0000.mp3", "segment_0001.mp3", "segment_0002.mp3"]
    for segment_name in segment_names:
        segment_file = os.path.join(chapter_output_dir, segment_name)
        with open(segment_file, "wb") as f:
            f.write(b"mock cartesia audio data")
            
    # Create the final chapter audio file in the correct location
    # Both in the audio directory and in the chapter directory
    final_audio_dir_file = os.path.join(audio_dir, "chapter_01.mp3")
    with open(final_audio_dir_file, "wb") as f:
        f.write(b"mock merged audio data")
        
    final_chapter_file = os.path.join(chapter_output_dir, "chapter_01.mp3")
    with open(final_chapter_file, "wb") as f:
        f.write(b"mock merged audio data")
    # --- End Setup ---

    # Mock the Cartesia TTS methods
    from unittest.mock import MagicMock
    
    # Create a mock for CartesiaTTS methods based on refactored structure
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._prepare_chapter_directory', return_value=(
        chapter_output_dir,  # chapter_dir
        os.path.join(audio_dir, 'chapter_01.mp3'),  # new_output_path
        'chapter_01'  # chapter_name
    ))
    
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._prepare_segment_request', return_value=(
        {
            'text': 'mocked text',
            'voice_id': 'mocked-voice-id',
            'output_file': 'mocked_output.mp3'
        },
        'mocked_output.mp3'  # temp_output path
    ))
    
    # Mock the generate_speech method that's actually used in CartesiaTTS
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS.generate_speech', return_value=True)
    
    # Mock the _combine_audio_files method
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._combine_audio_files', return_value=True)
    
    # Directly patch the high-level methods as well
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS.generate_audio_from_request', return_value=True)
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS.generate_audio_from_request_async', return_value=True)
    
    # Run the audio generation function with mocked components
    result = process_tts_files(
        book_dir=book_dir,
        provider=tts_provider,
        model="sonic",
        use_cloned_voices=False,
        force=True,
        single_file=None,
        use_async=False
    )

    # --- Verification ---
    assert os.path.exists(chapter_output_dir), "Chapter output directory was not created"

    # Check for segment files
    segment_files = [f for f in os.listdir(chapter_output_dir) if f.startswith("segment_") and f.endswith(".mp3")]
    assert len(segment_files) == 3, f"Expected 3 segment files, found {len(segment_files)}"
    
    # Check for segment files - using our modified naming pattern
    assert os.path.exists(os.path.join(chapter_output_dir, "segment_0000.mp3"))
    assert os.path.exists(os.path.join(chapter_output_dir, "segment_0001.mp3"))
    assert os.path.exists(os.path.join(chapter_output_dir, "segment_0002.mp3"))


    # Check for the final combined chapter file in both locations
    final_chapter_file = os.path.join(chapter_output_dir, "chapter_01.mp3")
    assert os.path.exists(final_chapter_file), "Final combined chapter file was not created in chapter directory"
    
    final_audio_file = os.path.join(audio_dir, "chapter_01.mp3")
    assert os.path.exists(final_audio_file), "Final combined chapter file was not created in audio directory"

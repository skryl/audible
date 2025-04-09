"""
Integration test for the audio assembly step.
"""

import os
import json
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.audio_generator import process_tts_files


def test_process_tts_files(temp_test_book_dir):
    """Test the processing of TTS request files into audio files."""
    # Set up the necessary directory structure and files
    tts_dir = os.path.join(temp_test_book_dir, "tts")
    audio_dir = os.path.join(temp_test_book_dir, "audio")
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    
    os.makedirs(tts_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(chapters_dir, exist_ok=True)
    
    # Create test TTS request files
    for i in range(1, 3):
        tts_file = os.path.join(tts_dir, f"chapter_{i:02d}_tts.json")
        with open(tts_file, "w", encoding="utf-8") as f:
            json.dump({
                "chapter_number": i,
                "title": f"Chapter {i}",
                "audio_file": f"chapter_{i:02d}.mp3",
                "status": "pending",
                "segments": [
                    {
                        "type": "narration",
                        "text": "Alice and Bob were discussing the weather.",
                        "voice_id": "alloy"
                    },
                    {
                        "type": "dialogue",
                        "character": "Alice",
                        "text": "It's quite nice today.",
                        "emotion": "pleasant",
                        "voice_id": "nova"
                    },
                    {
                        "type": "dialogue",
                        "character": "Bob",
                        "text": "Indeed it is. I think we should go for a walk.",
                        "emotion": "agreeable",
                        "voice_id": "onyx"
                    },
                    {
                        "type": "narration",
                        "text": "Charlie joined them later and brought some sandwiches.",
                        "voice_id": "alloy"
                    }
                ]
            }, f, indent=2)
    
    # Ensure the audio directory exists
    os.makedirs(audio_dir, exist_ok=True)
    
    # Create provider-specific directory
    provider = "openai"
    provider_dir = os.path.join(tts_dir, provider)
    os.makedirs(provider_dir, exist_ok=True)
    
    # Create dummy chapter files
    for i in range(1, 3):
        with open(os.path.join(chapters_dir, f"{i:02d}_Chapter {i}.txt"), "w") as f:
            f.write(f"Content for Chapter {i}")
    
    # Copy the TTS request files to the provider directory
    for i in range(1, 3):
        src_file = os.path.join(tts_dir, f"chapter_{i:02d}_tts.json")
        dst_file = os.path.join(provider_dir, f"chapter_{i:02d}_tts.json")
        with open(src_file, "r", encoding="utf-8") as f_src:
            with open(dst_file, "w", encoding="utf-8") as f_dst:
                f_dst.write(f_src.read())
                
    # Create chapter directories and mock output files
    for i in range(1, 3):
        chapter_dir = os.path.join(provider_dir, f"chapter_{i:02d}")
        os.makedirs(chapter_dir, exist_ok=True)
        
        # Create dummy segment files
        for j in range(4):  # We have 4 segments per chapter
            segment_file = os.path.join(chapter_dir, f"segment_{j:04d}.mp3")
            with open(segment_file, "wb") as f:
                f.write(b"mock audio data")
                
        # Create final chapter audio file
        chapter_audio = os.path.join(audio_dir, f"chapter_{i:02d}.mp3")
        with open(chapter_audio, "wb") as f:
            f.write(b"mock merged audio data")
    
    # Create a mock TTS engine that will create the necessary files
    def mock_generate_audio(tts_request, output_path):
        # Extract the chapter number from the request
        chapter_num = tts_request.get("chapter_number", 1)
        
        # Create chapter directory if it doesn't exist
        chapter_dir = os.path.join(provider_dir, f"chapter_{chapter_num:02d}")
        os.makedirs(chapter_dir, exist_ok=True)
        
        # Create segment files
        segments = tts_request.get("segments", [])
        for j, segment in enumerate(segments):
            segment_file = os.path.join(chapter_dir, f"segment_{j:04d}.mp3")
            with open(segment_file, "wb") as f:
                f.write(b"mock audio data")
                
        # Create final chapter audio file
        audio_file = tts_request.get("audio_file", f"chapter_{chapter_num:02d}.mp3")
        chapter_audio = os.path.join(audio_dir, audio_file)
        with open(chapter_audio, "wb") as f:
            f.write(b"mock merged audio data")
            
        return True
    
    async def mock_generate_audio_async(tts_request, output_path):
        return mock_generate_audio(tts_request, output_path)
    
    mock_tts_engine = MagicMock()
    mock_tts_engine.generate_audio_from_request.side_effect = mock_generate_audio
    mock_tts_engine.generate_audio_from_request_async.side_effect = mock_generate_audio_async
    
    # Test with synchronous processing
    with patch("audible.tts.tts_factory.TTSFactory.create", return_value=mock_tts_engine):
        # Set environment variable for TTS provider
        os.environ["AUDIBLE_TTS_PROVIDER"] = "openai"
        
        # Run the process_tts_files function
        result = process_tts_files(book_dir=temp_test_book_dir, force=True, use_async=False)
        
        # Assert that the processing was successful
        assert result is True
        
        # Check that the audio directory was created
        assert os.path.exists(audio_dir)
        
        # Verify that the TTS engine's generate_audio_from_request method was called for each file
        assert mock_tts_engine.generate_audio_from_request.call_count == 2
        
        # Check that each TTS file was updated with "processed" status
        for i in range(1, 3):
            tts_file = os.path.join(tts_dir, f"chapter_{i:02d}_tts.json")
            with open(tts_file, "r", encoding="utf-8") as f:
                tts_data = json.load(f)
                assert tts_data["status"] == "processed"
    
    # Reset mock and TTS files for asynchronous test
    mock_tts_engine.reset_mock()
    for i in range(1, 3):
        # Reset status in provider directory TTS files
        tts_file = os.path.join(provider_dir, f"chapter_{i:02d}_tts.json")
        with open(tts_file, "w", encoding="utf-8") as f:
            json.dump({
                "chapter_number": i,
                "title": f"Chapter {i}",
                "audio_file": f"chapter_{i:02d}.mp3",
                "status": "pending",
                "segments": [
                    {
                        "type": "narration",
                        "text": "Section from chapter " + str(i),
                        "voice_id": "alloy"
                    }
                ]
            }, f, indent=2)
    
    # Test with asynchronous processing
    with patch("audible.tts.tts_factory.TTSFactory.create", return_value=mock_tts_engine):
        # Set environment variable for TTS provider
        os.environ["AUDIBLE_TTS_PROVIDER"] = "openai"
        
        # Run the process_tts_files function with async flag
        result = process_tts_files(book_dir=temp_test_book_dir, force=True, use_async=True)
        
        # Assert that the processing was successful
        assert result is True
        
        # Check that the audio directory still exists
        assert os.path.exists(audio_dir)
        
        # For async processing, we should be using the async method
        assert mock_tts_engine.generate_audio_from_request_async.call_count > 0
        
        # Check that each TTS file was updated with "processed" status
        for i in range(1, 3):
            tts_file = os.path.join(tts_dir, f"chapter_{i:02d}_tts.json")
            with open(tts_file, "r", encoding="utf-8") as f:
                tts_data = json.load(f)
                assert tts_data["status"] == "processed"


def test_process_single_tts_file(temp_test_book_dir):
    """Test processing a single TTS file."""
    # Set up the necessary directory structure and files
    tts_dir = os.path.join(temp_test_book_dir, "tts")
    audio_dir = os.path.join(temp_test_book_dir, "audio")
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    
    os.makedirs(tts_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(chapters_dir, exist_ok=True)
    
    # Create dummy chapter files
    for i in range(1, 3):
        with open(os.path.join(chapters_dir, f"{i:02d}_Chapter {i}.txt"), "w") as f:
            f.write(f"Content for Chapter {i}")
    audio_dir = os.path.join(temp_test_book_dir, "audio")
    
    os.makedirs(tts_dir, exist_ok=True)
    
    # Create test TTS request file
    tts_file = os.path.join(tts_dir, "chapter_01_tts.json")
    with open(tts_file, "w", encoding="utf-8") as f:
        json.dump({
            "chapter_number": 1,
            "title": "Chapter 1",
            "audio_file": "chapter_01.mp3",
            "status": "pending",
            "segments": [
                {
                    "type": "narration",
                    "text": "This is a test chapter.",
                    "voice_id": "alloy"
                }
            ]
        }, f, indent=2)
    
    # Create a mock TTS engine
    mock_tts_engine = MagicMock()
    mock_tts_engine.generate_audio_from_request.return_value = True
    
    # Test with processing a single file
    with patch("audible.tts.tts_factory.TTSFactory.create", return_value=mock_tts_engine):
        # Set environment variable for TTS provider
        os.environ["AUDIBLE_TTS_PROVIDER"] = "openai"
        
        # Run the process_tts_files function with single_file parameter
        result = process_tts_files(
            book_dir=temp_test_book_dir,
            force=True,
            use_async=False,
            single_file=tts_file
        )
        
        # Assert that the processing was successful
        assert result is True
        
        # Check that the audio directory was created
        assert os.path.exists(audio_dir)
        
        # Verify that the TTS engine's generate_audio_from_request method was called once
        mock_tts_engine.generate_audio_from_request.assert_called_once()
        
        # Check that the TTS file was updated with "processed" status
        with open(tts_file, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
            assert tts_data["status"] == "processed"


def test_process_tts_files_with_different_providers(temp_test_book_dir):
    """Test processing TTS files with different TTS providers."""
    # Set up the necessary directory structure and files
    tts_dir = os.path.join(temp_test_book_dir, "tts")
    audio_dir = os.path.join(temp_test_book_dir, "audio")
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    
    os.makedirs(tts_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(chapters_dir, exist_ok=True)
    
    # Create dummy chapter files
    for i in range(1, 3):
        with open(os.path.join(chapters_dir, f"{i:02d}_Chapter {i}.txt"), "w") as f:
            f.write(f"Content for Chapter {i}")
    
    os.makedirs(tts_dir, exist_ok=True)
    
    # Create test TTS request file
    tts_file = os.path.join(tts_dir, "chapter_01_tts.json")
    with open(tts_file, "w", encoding="utf-8") as f:
        json.dump({
            "chapter_number": 1,
            "title": "Chapter 1",
            "audio_file": "chapter_01.mp3",
            "status": "pending",
            "segments": [
                {
                    "type": "narration",
                    "text": "This is a test chapter.",
                    "voice_id": "alloy"
                }
            ]
        }, f, indent=2)
    
    # Create mock TTS engines for different providers
    mock_openai_tts = MagicMock()
    mock_openai_tts.generate_audio_from_request.return_value = True
    
    mock_cartesia_tts = MagicMock()
    mock_cartesia_tts.generate_audio_from_request.return_value = True
    
    # Test with OpenAI provider
    with patch("audible.tts.tts_factory.TTSFactory.create", return_value=mock_openai_tts):
        result_openai = process_tts_files(
            book_dir=temp_test_book_dir,
            provider="openai",
            force=True
        )
        
        # Assert that the processing was successful
        assert result_openai is True
        
        # Verify that the OpenAI TTS engine was used
        mock_openai_tts.generate_audio_from_request.assert_called_once()
    
    # Reset the TTS file status
    with open(tts_file, "r", encoding="utf-8") as f:
        tts_data = json.load(f)
    
    tts_data["status"] = "pending"
    
    with open(tts_file, "w", encoding="utf-8") as f:
        json.dump(tts_data, f, indent=2)
    
    # Test with Cartesia provider
    with patch("audible.tts.tts_factory.TTSFactory.create", return_value=mock_cartesia_tts):
        result_cartesia = process_tts_files(
            book_dir=temp_test_book_dir,
            provider="cartesia",
            force=True
        )
        
        # Assert that the processing was successful
        assert result_cartesia is True
        
        # Verify that the Cartesia TTS engine was used
        mock_cartesia_tts.generate_audio_from_request.assert_called_once()

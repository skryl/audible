import os
import json
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.tts_preparer import prepare_tts

def test_prepare_tts(temp_test_book_dir):
    """Test that the TTS preparation step creates TTS request files from scripts."""
    # Set up the necessary directory structure and files
    scripts_dir = os.path.join(temp_test_book_dir, "scripts")
    tts_dir = os.path.join(temp_test_book_dir, "tts")
    voices_dir = os.path.join(temp_test_book_dir, "voices")
    characters_dir = os.path.join(temp_test_book_dir, "characters")
    
    os.makedirs(scripts_dir, exist_ok=True)
    os.makedirs(voices_dir, exist_ok=True)
    os.makedirs(characters_dir, exist_ok=True)
    
    # Create chapters directory with dummy files - needed for get_chapter_filename
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    
    # Create dummy chapter files to match the expected script files
    for i in range(1, 3):
        chapter_path = os.path.join(chapters_dir, f"{i:02d}_Chapter {i}.txt")
        with open(chapter_path, "w", encoding="utf-8") as f:
            f.write(f"Dummy content for Chapter {i}")
    
    # Create test script files
    for i in range(1, 3):
        script_path = os.path.join(scripts_dir, f"chapter_{i}_script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump({
                "chapter_number": i,
                "title": f"Chapter {i}",
                "segments": [
                    {
                        "type": "narration",
                        "text": "Alice and Bob were discussing the weather."
                    },
                    {
                        "type": "dialogue",
                        "character": "Alice",
                        "text": "It's quite nice today.",
                        "emotion": "pleasant"
                    },
                    {
                        "type": "dialogue",
                        "character": "Bob",
                        "text": "Indeed it is. I think we should go for a walk.",
                        "emotion": "agreeable"
                    },
                    {
                        "type": "narration",
                        "text": "Charlie joined them later and brought some sandwiches."
                    }
                ]
            }, f, indent=2)
    
    # Create characters.json file
    characters_file = os.path.join(characters_dir, "characters.json")
    with open(characters_file, "w", encoding="utf-8") as f:
        json.dump({
            "Alice": {
                "name": "Alice",
                "gender": "female",
                "voice": "soft, melodic"
            },
            "Bob": {
                "name": "Bob",
                "gender": "male",
                "voice": "deep, steady"
            },
            "Narrator": {
                "name": "Narrator",
                "gender": "male",
                "voice": "clear, authoritative"
            }
        }, f, indent=2)
    
    # Create voice_mappings.json file
    voice_mappings_file = os.path.join(voices_dir, "voice_mappings.json")
    with open(voice_mappings_file, "w", encoding="utf-8") as f:
        json.dump({
            "Alice": {
                "openai": {"voice_id": "nova"},
                "cartesia": {"voice_id": "mock-alice-voice-id", "voice_name": "Alice Voice", "clone_id": ""}
            },
            "Bob": {
                "openai": {"voice_id": "onyx"},
                "cartesia": {"voice_id": "mock-bob-voice-id", "voice_name": "Bob Voice", "clone_id": ""}
            },
            "Narrator": {
                "openai": {"voice_id": "alloy"},
                "cartesia": {"voice_id": "mock-narrator-voice-id", "voice_name": "Narrator Voice", "clone_id": ""}
            }
        }, f, indent=2)
    
    # Run the TTS preparation with OpenAI provider
    os.environ["AUDIBLE_TTS_PROVIDER"] = "openai"
    result_openai = prepare_tts(book_dir=temp_test_book_dir, force=True, provider="openai")
    
    # Assert that the preparation was successful
    assert result_openai is True
    
    # Check that the TTS directory was created
    assert os.path.exists(tts_dir)
    
    # Check that TTS request files were created for each chapter with provider-specific subdirectory
    openai_tts_dir = os.path.join(tts_dir, "openai")
    assert os.path.exists(openai_tts_dir), f"OpenAI TTS directory was not created at {openai_tts_dir}"
    
    for i in range(1, 3):
        tts_file = os.path.join(openai_tts_dir, f"chapter_{i}_tts.json")
        assert os.path.exists(tts_file), f"TTS file not found at {tts_file}"
        
        # Verify the content of each TTS file
        with open(tts_file, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
            
            # Check that the TTS request contains the expected metadata
            assert "chapter_number" in tts_data
            assert tts_data["chapter_number"] == i
            assert "title" in tts_data
            assert "audio_file" in tts_data
            assert tts_data["audio_file"] == f"chapter_{i:02d}.mp3"  # Using padded format to match implementation
            assert "status" in tts_data
            assert tts_data["status"] == "pending"
            
            # Check that the request contains segments
            assert "segments" in tts_data
            assert len(tts_data["segments"]) == 4  # Same as in our test script
            
            # Check that each segment has the required fields
            for segment in tts_data["segments"]:
                assert "type" in segment
                assert "text" in segment
                
                # Check dialogue segments
                if segment["type"] == "dialogue":
                    assert "character" in segment
                    assert "voice_id" in segment
                    if segment["character"] == "Alice":
                        if isinstance(segment["voice_id"], dict):
                            assert segment["voice_id"]["voice_id"] == "nova"
                        else:
                            assert segment["voice_id"] == "nova"
                    elif segment["character"] == "Bob":
                        if isinstance(segment["voice_id"], dict):
                            assert segment["voice_id"]["voice_id"] == "onyx"
                        else:
                            assert segment["voice_id"] == "onyx"
                
                # Check narration segments
                if segment["type"] == "narration":
                    assert "voice_id" in segment
                    if isinstance(segment["voice_id"], dict):
                        assert segment["voice_id"]["voice_id"] == "alloy"  # Narrator voice ID
                    else:
                        assert segment["voice_id"] == "alloy"  # Narrator voice ID
    
    # Run the TTS preparation with Cartesia provider
    os.environ["AUDIBLE_TTS_PROVIDER"] = "cartesia"
    result_cartesia = prepare_tts(book_dir=temp_test_book_dir, force=True, provider="cartesia")
    
    # Assert that the preparation was successful
    assert result_cartesia is True
    
    # Check that TTS request files were created in cartesia subdirectory with Cartesia voice IDs
    cartesia_tts_dir = os.path.join(tts_dir, "cartesia")
    assert os.path.exists(cartesia_tts_dir), f"Cartesia TTS directory was not created at {cartesia_tts_dir}"
    
    for i in range(1, 3):
        tts_file = os.path.join(cartesia_tts_dir, f"chapter_{i}_tts.json")
        assert os.path.exists(tts_file), f"TTS file not found at {tts_file}"
        
        with open(tts_file, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
            
            # Check that each dialogue segment now has Cartesia voice IDs
            for segment in tts_data["segments"]:
                if segment["type"] == "dialogue":
                    assert "voice_id" in segment
                    if segment["character"] == "Alice":
                        if isinstance(segment["voice_id"], dict):
                            assert segment["voice_id"]["voice_id"] == "mock-alice-voice-id"
                        else:
                            assert segment["voice_id"] == "mock-alice-voice-id"
                    elif segment["character"] == "Bob":
                        if isinstance(segment["voice_id"], dict):
                            assert segment["voice_id"]["voice_id"] == "mock-bob-voice-id"
                        else:
                            assert segment["voice_id"] == "mock-bob-voice-id"
                
                if segment["type"] == "narration":
                    if isinstance(segment["voice_id"], dict):
                        assert segment["voice_id"]["voice_id"] == "mock-narrator-voice-id"
                    else:
                        assert segment["voice_id"] == "mock-narrator-voice-id"

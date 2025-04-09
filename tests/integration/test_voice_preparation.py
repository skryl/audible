"""
Integration test for the voice mapping preparation step.
"""

import os
import json
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.tts_preparer import prepare_voice_mappings


def test_prepare_voice_mappings(temp_test_book_dir):
    """Test that the voice mapping preparation step creates a voice_mappings.json file with appropriate voices."""
    # First set up the necessary directory structure and files
    characters_dir = os.path.join(temp_test_book_dir, "characters")
    voices_dir = os.path.join(temp_test_book_dir, "voices")
    
    os.makedirs(characters_dir, exist_ok=True)
    os.makedirs(voices_dir, exist_ok=True)
    
    # Create a characters.json file with test data
    characters_file = os.path.join(characters_dir, "characters.json")
    with open(characters_file, "w", encoding="utf-8") as f:
        json.dump({
            "Alice": {
                "name": "Alice",
                "gender": "female",
                "age": "mid-twenties",
                "personality": "friendly, outgoing",
                "voice": "soft, melodic",
                "appearance": "long brown hair, blue eyes",
                "role": "protagonist",
                "chapters": [1, 2]
            },
            "Bob": {
                "name": "Bob",
                "gender": "male",
                "age": "early thirties",
                "personality": "thoughtful, calm",
                "voice": "deep, steady",
                "appearance": "short blonde hair, green eyes",
                "role": "supporting character",
                "chapters": [1, 2]
            },
            "Charlie": {
                "name": "Charlie",
                "gender": "male",
                "age": "late twenties",
                "personality": "generous, thoughtful",
                "voice": "cheerful, energetic",
                "appearance": "tall with curly hair",
                "role": "supporting character",
                "chapters": [2]
            },
            "Narrator": {
                "name": "Narrator",
                "gender": "male",
                "voice": "clear, authoritative",
                "chapters": [1, 2]
            }
        }, f, indent=2)
    
    # Run the voice mapping preparation
    result = prepare_voice_mappings(book_dir=temp_test_book_dir, force=True)
    
    # Assert that the preparation was successful
    assert result is True
    
    # Check that the voice_mappings.json file was created
    voice_mappings_file = os.path.join(voices_dir, "voice_mappings.json")
    assert os.path.exists(voice_mappings_file)
    
    # Verify the content of the voice_mappings.json file
    with open(voice_mappings_file, "r", encoding="utf-8") as f:
        voice_mappings = json.load(f)
        
        # Check that all characters have voice mappings
        assert "Alice" in voice_mappings
        assert "Bob" in voice_mappings
        assert "Charlie" in voice_mappings
        assert "Narrator" in voice_mappings
        
        # Check that each character has both OpenAI and Cartesia voice settings
        for character in ["Alice", "Bob", "Charlie", "Narrator"]:
            assert "openai" in voice_mappings[character]
            assert "cartesia" in voice_mappings[character]
            
            # Verify structure of voice mappings - each provider has a string voice ID
            assert isinstance(voice_mappings[character]["openai"], str)
            assert isinstance(voice_mappings[character]["cartesia"], str)
            
        # Verify that voices have been assigned - no need to check specific voice assignments
        # as the implementation may change how voices are assigned
        assert voice_mappings["Alice"]["openai"] in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        assert voice_mappings["Bob"]["openai"] in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        assert voice_mappings["Charlie"]["openai"] in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        assert voice_mappings["Narrator"]["openai"] in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

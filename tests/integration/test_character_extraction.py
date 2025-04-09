"""
Integration test for the character extraction step.
"""

import os
import json
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.character_extractor import extract_characters


def test_extract_characters(temp_test_book_dir, mock_llm_client):
    """Test that the character extraction step creates character profiles and a consolidated characters.json file."""
    # First set up the necessary directory structure and files
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    analysis_dir = os.path.join(temp_test_book_dir, "analysis")
    
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    
    # Create test chapter files
    for i in range(1, 3):
        padded_num = f"0{i}"
        chapter_path = os.path.join(chapters_dir, f"{padded_num}_Chapter {i}.txt")
        with open(chapter_path, "w", encoding="utf-8") as f:
            f.write(f"""
Chapter {i}

Alice and Bob were discussing the weather.

"It's quite nice today," said Alice.

"Indeed it is," replied Bob. "I think we should go for a walk."

Charlie joined them later and brought some sandwiches.
""")
    
    # Create test analysis files with character information
    for i in range(1, 3):
        analysis_path = os.path.join(analysis_dir, f"chapter_{i:02d}_analysis.json")
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump({
                "scenes": [
                    {
                        "scene_number": 1,
                        "description": "Alice and Bob discussing the weather",
                        "characters": ["Alice", "Bob"],
                        "dialog": True,
                        "action": "conversation"
                    },
                    {
                        "scene_number": 2,
                        "description": "Charlie joins with sandwiches",
                        "characters": ["Alice", "Bob", "Charlie"],
                        "dialog": False,
                        "action": "arrival"
                    }
                ],
                "characters": ["Alice", "Bob", "Charlie"],
                "major_characters": ["Alice", "Bob"]
            }, f, indent=2)
    
    # Configure the mock LLM client to return character information for each chapter
    mock_llm_client.configure_responses([
        # Response for chapter 1
        json.dumps({
            "Alice": {
                "name": "Alice",
                "gender": "female",
                "age": "mid-twenties",
                "personality": "friendly, outgoing",
                "voice": "soft, melodic",
                "appearance": "long brown hair, blue eyes",
                "role": "protagonist",
                "chapters": [1]
            },
            "Bob": {
                "name": "Bob",
                "gender": "male",
                "age": "early thirties",
                "personality": "thoughtful, calm",
                "voice": "deep, steady",
                "appearance": "short blonde hair, green eyes",
                "role": "supporting character",
                "chapters": [1]
            }
        }),
        # Response for chapter 2
        json.dumps({
            "Alice": {
                "name": "Alice",
                "gender": "female",
                "personality": "curious, adventurous",
                "chapters": [2]
            },
            "Bob": {
                "name": "Bob",
                "gender": "male",
                "personality": "logical, practical",
                "chapters": [2]
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
            }
        })
    ])
    
    # Run the character extraction
    result = extract_characters(book_dir=temp_test_book_dir, force=True)
    
    # Assert that the extraction was successful
    assert result is True
    
    # Check that the characters directory was created
    characters_dir = os.path.join(temp_test_book_dir, "characters")
    assert os.path.exists(characters_dir)
    
    # Check that the consolidated characters.json file was created
    characters_file = os.path.join(characters_dir, "characters.json")
    assert os.path.exists(characters_file)
    
    # Verify the content of the characters.json file
    with open(characters_file, "r", encoding="utf-8") as f:
        characters_data = json.load(f)
        
        # Check that all major characters are included
        assert "Alice" in characters_data
        assert "Bob" in characters_data
        
        # Check that character information is merged correctly
        assert set(characters_data["Alice"]["chapters"]) == {1, 2}
        assert set(characters_data["Bob"]["chapters"]) == {1, 2}
        
        # Check that character traits are included
        assert "gender" in characters_data["Alice"]
        assert characters_data["Alice"]["gender"] == "female"
    
    # Check that individual character files were created
    assert os.path.exists(os.path.join(characters_dir, "alice.json"))
    assert os.path.exists(os.path.join(characters_dir, "bob.json"))
    
    # Verify the content of an individual character file
    with open(os.path.join(characters_dir, "alice.json"), "r", encoding="utf-8") as f:
        alice_data = json.load(f)
        assert alice_data["name"] == "Alice"
        assert "gender" in alice_data
        assert "personality" in alice_data

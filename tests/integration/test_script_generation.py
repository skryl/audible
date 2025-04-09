"""
Integration test for the script generation step.
"""

import os
import json
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.script_generator import generate_scripts


def test_generate_scripts(temp_test_book_dir, mock_llm_client):
    """Test that the script generation step creates script files with properly structured content."""
    # Set up the necessary directory structure and files
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    analysis_dir = os.path.join(temp_test_book_dir, "analysis")
    characters_dir = os.path.join(temp_test_book_dir, "characters")
    
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    os.makedirs(characters_dir, exist_ok=True)
    
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
    
    # Create test analysis files
    for i in range(1, 3):
        analysis_path = os.path.join(analysis_dir, f"chapter_{i}_analysis.json")
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
    
    # Create characters.json file
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
    
    # Configure the mock LLM client to return script data
    mock_llm_client.configure_responses([
        # Response for chapter 1
        json.dumps({
            "title": "Chapter 1",
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
        }),
        # Response for chapter 2
        json.dumps({
            "title": "Chapter 2",
            "segments": [
                {
                    "type": "narration",
                    "text": "Alice and Bob continued their conversation from yesterday."
                },
                {
                    "type": "dialogue",
                    "character": "Bob",
                    "text": "Should we invite Charlie again today?",
                    "emotion": "curious"
                },
                {
                    "type": "dialogue",
                    "character": "Alice",
                    "text": "Yes, the sandwiches were delicious.",
                    "emotion": "enthusiastic"
                },
                {
                    "type": "narration",
                    "text": "They called Charlie, who agreed to join them again."
                },
                {
                    "type": "dialogue",
                    "character": "Charlie",
                    "text": "I'll bring cookies this time!",
                    "emotion": "excited"
                }
            ]
        })
    ])
    
    # Run the script generation
    result = generate_scripts(book_dir=temp_test_book_dir, force=True)
    
    # Assert that the generation was successful
    assert result is True
    
    # Check that the scripts directory was created
    scripts_dir = os.path.join(temp_test_book_dir, "scripts")
    assert os.path.exists(scripts_dir)
    
    # Check that script files were created for each chapter
    for i in range(1, 3):
        script_file = os.path.join(scripts_dir, f"chapter_{i}_script.json")
        assert os.path.exists(script_file)
        
        # Verify the content of each script file
        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)
            
            # Check that the script contains the expected metadata
            assert "chapter_number" in script_data
            assert script_data["chapter_number"] == i
            assert "title" in script_data
            assert script_data["title"] == f"Chapter {i}"
            
            # Check that the script contains segments
            assert "segments" in script_data
            assert len(script_data["segments"]) > 0
            
            # Check that each segment has the required fields
            for segment in script_data["segments"]:
                assert "type" in segment
                assert "text" in segment
                
                # Check dialogue segments
                if segment["type"] == "dialogue":
                    assert "character" in segment
                    assert segment["character"] in ["Alice", "Bob", "Charlie"]
                    assert "emotion" in segment
                
                # Check narration segments
                if segment["type"] == "narration":
                    assert segment["text"] is not None

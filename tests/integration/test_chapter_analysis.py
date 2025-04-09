"""
Integration test for the chapter analysis step.
"""

import os
import json
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.chapter_analyzer import analyze_chapters


def test_analyze_chapters(temp_test_book_dir, mock_llm_client):
    """Test that the chapter analysis step creates analysis files with scenes and characters."""
    # Set up chapter directory first
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    os.makedirs(chapters_dir, exist_ok=True)
    
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
    
    # Configure the mock LLM client to return a valid analysis response
    mock_llm_client.configure_responses([
        # Mock response for scene breakdown of chapter 1
        json.dumps({
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
            ]
        }),
        # Mock response for character extraction of chapter 1
        json.dumps({
            "all_characters": ["Alice", "Bob", "Charlie"],
            "major_characters": ["Alice", "Bob"]
        }),
        # Mock response for scene breakdown of chapter 2
        json.dumps({
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
            ]
        }),
        # Mock response for character extraction of chapter 2
        json.dumps({
            "all_characters": ["Alice", "Bob", "Charlie"],
            "major_characters": ["Alice", "Bob"]
        })
    ])
    
    # Run the chapter analysis
    result = analyze_chapters(book_dir=temp_test_book_dir, force=True)
    
    # Assert that the analysis was successful
    assert result is True
    
    # Check that the analysis directory was created
    analysis_dir = os.path.join(temp_test_book_dir, "analysis")
    assert os.path.exists(analysis_dir)
    
    # Print the contents of the analysis directory for debugging
    print("Analysis directory contents:")
    analysis_files = os.listdir(analysis_dir)
    for f in analysis_files:
        print(f"  - {f}")
        
    # Check that analysis files were created for each chapter
    # Based on the debug output, the file naming pattern uses non-padded chapter numbers
    for i in range(1, 3):
        # The chapter_analyzer extracts chapter numbers but does not pad them in the output filenames
        analysis_file = os.path.join(analysis_dir, f"chapter_{i}_analysis.json")
        assert os.path.exists(analysis_file), f"Analysis file {analysis_file} not found in {analysis_files}"
        
        # Verify the content of each analysis file
        with open(analysis_file, "r", encoding="utf-8") as f:
            analysis_data = json.load(f)
            
            # Check that the analysis contains the expected sections
            assert "scenes" in analysis_data
            assert "characters" in analysis_data
            assert "major_characters" in analysis_data
            
            # Check that the characters were extracted correctly
            assert "Alice" in analysis_data["characters"]
            assert "Bob" in analysis_data["characters"]
            assert "Charlie" in analysis_data["characters"]
            
            # Check that major characters were identified
            assert "Alice" in analysis_data["major_characters"]
            assert "Bob" in analysis_data["major_characters"]

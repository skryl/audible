"""
Integration test for the book preparation step.
"""

import os
import sys
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))
from audible.core.book_preparer import prepare_book


def test_prepare_book(temp_test_book_dir):
    """Test that the book preparation step creates chapter files."""
    # Prepare book.txt in the test directory
    book_txt_path = os.path.join(temp_test_book_dir, "book.txt")
    
    # Write a simple test book with clear chapter markers
    with open(book_txt_path, "w", encoding="utf-8") as f:
        f.write("""
CHAPTER 1

This is the content of chapter 1.
It has multiple paragraphs that need to exceed the 500 character threshold used in the chapter detection logic.

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus lacinia odio vitae vestibulum vestibulum. 
Donec in efficitur ipsum. Sed dapibus purus quam, a pretium justo sodales eget. Suspendisse potenti. 
Pellentesque habitant morbi tristique senectus et netus et malesuada fames ac turpis egestas. 
Donec eget erat eros. Nunc non luctus nisl, nec facilisis nulla. 
Proin egestas nisi id felis dapibus, vel tincidunt velit dapibus. Nullam non elementum ante.

And continues for quite a bit longer to ensure it's properly detected as a chapter.

CHAPTER 2

This is the content of chapter 2.
It also has multiple paragraphs that need to meet the minimum length requirements.

Curabitur convallis purus sit amet dignissim sagittis. Nullam ut turpis ac tortor tincidunt varius.
Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; 
Cras eget rhoncus magna, non ultricies orci. Integer aliquam erat non augue iaculis dictum. 
Aenean libero ligula, pharetra in fermentum a, lobortis non urna. 
Etiam tempus iaculis lectus, a hendrerit mauris condimentum ac. Fusce non condimentum metus.

And continues with more lengthy content as well.

CHAPTER 3

This is the content of chapter 3.
The final chapter in our test book needs sufficient length too.

Proin facilisis est nec pellentesque elementum. Quisque congue tellus eu sapien varius, 
sit amet mollis velit tincidunt. Vivamus finibus augue in dui sollicitudin, at commodo eros luctus. 
Maecenas varius enim vitae justo iaculis, vel volutpat mauris vulputate. 
Integer sodales nibh non erat vulputate, nec pretium mi efficitur. 
Donec porttitor justo sed ligula finibus, vel efficitur ex ultrices. 
Nullam sed magna vitae risus facilisis fermentum non quis sem. Etiam quis consequat lectus.

This concludes our test book with three properly sized chapters.
""")
    
    # Run the book preparation
    result = prepare_book(book_dir=temp_test_book_dir, force=True)
    
    # Assert that the preparation was successful
    assert result is True
    
    # Check that the chapters directory was created
    chapters_dir = os.path.join(temp_test_book_dir, "chapters")
    assert os.path.exists(chapters_dir)
    
    # Check that chapter files were created
    chapter_files = [f for f in os.listdir(chapters_dir) if f.endswith(".txt")]
    assert len(chapter_files) == 3
    
    # Verify each chapter file exists and has the correct content
    for i in range(1, 4):
        # The actual filename uses lowercase 'chapter' and no padding on the number
        chapter_filename = f"{i}_chapter_{i}.txt"
        chapter_path = os.path.join(chapters_dir, chapter_filename)
        assert os.path.exists(chapter_path), f"Expected chapter file {chapter_filename} not found"
        
        # Check that the content of each chapter file is correct
        with open(chapter_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert f"This is the content of chapter {i}" in content

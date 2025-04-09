import pytest
import os
import shutil

# Make logs visible during tests
import logging
logging.basicConfig(level=logging.INFO)
# You might want to capture logs specifically per test instead
# https://docs.pytest.org/en/stable/how-to/logging.html

@pytest.fixture(scope="session")
def base_dir():
    """Return the base directory of the project."""
    return os.path.dirname(os.path.dirname(__file__))

@pytest.fixture(scope="session")
def test_data_dir(base_dir):
    """Return the path to the test data directory."""
    return os.path.join(base_dir, "tests", "book")

@pytest.fixture
def temp_test_book_dir(test_data_dir, tmp_path):
    """Copy the test book data to a temporary directory for modification."""
    temp_dir = tmp_path / "book"
    shutil.copytree(test_data_dir, temp_dir)
    # Ensure necessary subdirectories exist for outputs
    os.makedirs(temp_dir / "llm", exist_ok=True)
    os.makedirs(temp_dir / "tts" / "mock_openai", exist_ok=True)
    os.makedirs(temp_dir / "tts" / "mock_cartesia", exist_ok=True)
    os.makedirs(temp_dir / "voice_clone", exist_ok=True)
    return str(temp_dir)

@pytest.fixture(autouse=True)
def mock_env_api_keys(monkeypatch):
    """Mock API keys environment variables."""
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("CARTESIA_API_KEY", "mock-cartesia-key")
    # Add other necessary mock env vars here (e.g., for LLM)
    monkeypatch.setenv("GOOGLE_API_KEY", "mock-google-key") # Assuming Gemini might be used
    monkeypatch.setenv("AUDIBLE_USE_ASYNC", "false") # Default to sync for easier testing unless overridden


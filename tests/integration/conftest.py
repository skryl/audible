import pytest
import os
import subprocess
from unittest.mock import MagicMock, AsyncMock

# --- Mock LLM Client ---
@pytest.fixture
def mock_llm_client(mocker):
    """Mocks the LLM client API functions used in chapter analysis and TTS preparation."""
    
    # Create a mock LLM class with the methods needed by the application
    class MockLLM:
        def __init__(self):
            self.responses = []
        
        def configure_responses(self, responses):
            self.responses = responses.copy()
        
        def call(self, prompt, system_message=None, response_format=None, max_retries=1):
            """Mock the synchronous call method used by OpenAILLM"""
            if self.responses:
                response = self.responses.pop(0)
                return response
            return {}
        
        async def call_async(self, prompt, system_message=None, response_format=None, max_retries=1):
            """Mock the asynchronous call method used by OpenAILLM"""
            if self.responses:
                response = self.responses.pop(0)
                return response
            return {}
            
        def chat_completion(self, messages, **kwargs):
            """For backwards compatibility"""
            return self.call(messages[0]["content"] if messages else "")
            
        async def chat_completion_async(self, messages, **kwargs):
            """For backwards compatibility"""
            return await self.call_async(messages[0]["content"] if messages else "")
    
    # Create an instance of our mock LLM
    mock_llm = MockLLM()
    
    # Patch the LLM factory to return our mock
    mock_llm_factory = mocker.patch('audible.llm.llm_factory.LLMFactory.create')
    mock_llm_factory.return_value = mock_llm
    
    # Also patch the direct OpenAI calls to prevent any accidental real API calls
    mocker.patch('openai.OpenAI')
    mocker.patch('openai.AsyncOpenAI')
    
    # Return our configured mock for the test to use
    return mock_llm


# --- Mock TTS Clients ---

def create_dummy_mp3(output_path, text_length=100):
    """Creates a small dummy MP3 file for testing."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Create a very small, technically invalid but sufficient file
    # A real dummy mp3 might be better if needed
    content = b'ID3' + os.urandom(text_length * 5) # Approximate size
    with open(output_path, 'wb') as f:
        f.write(content)
    print(f"[Mock TTS] Created dummy MP3: {output_path}")

@pytest.fixture
def mock_openai_tts(mocker):
    """Mocks the OpenAI TTS client methods."""
    # Mock the synchronous client method
    def mock_speech_create(*args, **kwargs):
        output_file = kwargs.get('output_file') # Adjust based on actual call signature
        if not output_file: # Try getting from positional args if needed
             # Find the argument that looks like a path ending in .mp3
             path_args = [a for a in args if isinstance(a, str) and a.endswith(".mp3")]
             if path_args:
                 output_file = path_args[0]
             else: # Fallback or error if path isn't found
                 output_file = "mock_openai_output.mp3"

        # Simulate API call by creating a dummy file
        create_dummy_mp3(output_file)
        # Mock response object if the code uses it (e.g., response.stream_to_file)
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock(side_effect=lambda path: create_dummy_mp3(path))
        return mock_response # Or just return None if the return value isn't used

    # Mock the asynchronous client method
    async def mock_speech_create_async(*args, **kwargs):
        output_file = kwargs.get('output_file', "mock_openai_output_async.mp3") # Adjust as needed
        create_dummy_mp3(output_file)
        mock_response = MagicMock()
        mock_response.stream_to_file = MagicMock(side_effect=lambda path: create_dummy_mp3(path))
        return mock_response # Or just return None

    mocker.patch('openai.resources.audio.speech.Speech.create', side_effect=mock_speech_create)
    # Adjust the async path if it's different
    mocker.patch('openai.resources.audio.speech.AsyncSpeech.create', side_effect=mock_speech_create_async)


@pytest.fixture
def mock_cartesia_tts(mocker):
    """Mocks the Cartesia TTS client methods."""

    # Mock synchronous bytes generation
    def mock_tts_bytes(*args, **kwargs):
        output_file = kwargs.get('output_file', "mock_cartesia_output.mp3") # Need to extract output path
        # Extract output_file path - this might be tricky as it's within the 'request' dict usually
        # We'll assume it's passed somehow or default
        request_arg = next((a for a in args if isinstance(a, dict)), kwargs.get('request'))
        if request_arg and 'output_file' in request_arg:
            output_file = request_arg['output_file']
            
        create_dummy_mp3(output_file)
        # Cartesia returns a generator yielding bytes
        dummy_bytes = b'dummy_cartesia_audio_chunk'
        return [dummy_bytes] # Return a list to simulate the iterable

    # Mock asynchronous bytes generation
    async def mock_tts_bytes_async(*args, **kwargs):
        output_file = "mock_cartesia_output_async.mp3" # Default
        request_arg = next((a for a in args if isinstance(a, dict)), kwargs.get('request'))
        if request_arg and 'output_file' in request_arg:
            output_file = request_arg['output_file']

        create_dummy_mp3(output_file)
        dummy_bytes = b'dummy_cartesia_async_chunk'
        # Return an async generator
        async def async_generator():
            yield dummy_bytes
        return async_generator()

    # Patch the correct methods within the CartesiaTTS class
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._prepare_segment_request', return_value={'output_file': 'mocked_output.mp3'})
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._generate_audio', side_effect=mock_tts_bytes)
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._generate_audio_async', side_effect=mock_tts_bytes_async)
    mocker.patch('audible.tts.cartesia_tts.CartesiaTTS._combine_audio_files', return_value=None)

# --- Mock External Commands ---

@pytest.fixture
def mock_ffmpeg(mocker):
    """Mocks subprocess.run calls specifically for ffmpeg."""
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        command = args[0]
        if isinstance(command, list) and command[0] == 'ffmpeg':
            print(f"[Mock FFMPEG] Skipping command: {' '.join(command)}")
            # Simulate success, potentially create the output file if needed
            output_file_index = -1
            try:
                # Common ffmpeg pattern: -i input ... output
                 output_file_index = command.index("-c") + 2 # Assuming '-c copy output'
                 if output_file_index >= len(command):
                     output_file_index = -1 # Fallback: last arg
            except ValueError:
                 output_file_index = -1 # Fallback: last arg

            if output_file_index != -1 and output_file_index < len(command):
                 output_file = command[output_file_index]
                 # Create a dummy output file to signify success
                 print(f"[Mock FFMPEG] Creating dummy output: {output_file}")
                 os.makedirs(os.path.dirname(output_file), exist_ok=True)
                 with open(output_file, 'wb') as f:
                     f.write(b'dummy_ffmpeg_output')

            # Return a CompletedProcess object indicating success
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
        else:
            # Call the original subprocess.run for non-ffmpeg commands
            return original_run(*args, **kwargs)

    # Patch subprocess.run
    mocker.patch('subprocess.run', side_effect=mock_run)



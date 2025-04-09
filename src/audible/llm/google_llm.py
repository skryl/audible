"""
Google LLM provider implementation.
"""

import os
import json
import time
import asyncio
from google.cloud import aiplatform
from google.oauth2 import service_account
from audible.utils.common import log, get_token_count, truncate_to_token_limit

class GoogleLLM:
    """Class for interacting with Google's language models."""

    def __init__(self, model="gemini-1.5-pro", temperature=0.0):
        """Initialize Google LLM provider."""
        self.model = model
        self.temperature = temperature
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Google AI Platform client."""
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

        try:
            if os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                aiplatform.init(credentials=credentials)
                log(f"Initialized Google AI Platform client using credentials from {credentials_path}")
            else:
                # Fall back to application default credentials
                aiplatform.init()
                log("Initialized Google AI Platform client using application default credentials")
        except Exception as e:
            log(f"Error initializing Google AI Platform client: {e}", level="ERROR")
            raise

    def get_token_limit(self):
        """Get the token limit for the current model."""
        model_limits = {
            "gemini-1.5-pro": 1000000,
            "gemini-1.5-flash": 1000000,
            "gemini-1.0-pro": 32000,
            "gemini-1.0-ultra": 32000,
        }
        return model_limits.get(self.model, 32000)  # Default to 32000 if model not found

    def _prepare_call_params(self, prompt, system_message=None, response_format=None):
        """Prepare parameters for API calls (both sync and async)."""
        log(f"Preparing API call to Google model {self.model}")

        # Calculate total tokens and handle token limits
        token_limit = self.get_token_limit()

        # Reserve tokens for system message and response
        system_tokens = get_token_count(system_message) if system_message else 0
        reserved_tokens = system_tokens + 4000  # Reserve ~4000 tokens for response

        # Calculate available tokens for prompt
        available_tokens = token_limit - reserved_tokens

        # Truncate prompt if needed
        prompt_tokens = get_token_count(prompt)
        if prompt_tokens > available_tokens:
            log(f"Prompt too long ({prompt_tokens} tokens), truncating to fit within limit ({available_tokens} tokens)", level="WARNING")
            prompt = truncate_to_token_limit(prompt, available_tokens)

        # Generation config
        generation_config = {
            "temperature": self.temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }

        # Prepare contents
        contents = []

        # Add system message if provided
        if system_message:
            contents.append({"role": "system", "parts": [{"text": system_message}]})

        # Add user prompt
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        # Add JSON response format instruction if needed
        if response_format and response_format.get("type") == "json_object":
            if system_message:
                # Update the system message
                system_instruction = system_message + "\nYou must respond with valid JSON."
                # Replace the first system message
                contents[0] = {"role": "system", "parts": [{"text": system_instruction}]}
            else:
                # Add a new system message
                contents.insert(0, {"role": "system", "parts": [{"text": "You must respond with valid JSON."}]})

        # Log token usage
        total_tokens = system_tokens + get_token_count(prompt)
        log(f"Using {total_tokens} tokens for API call (limit: {token_limit})")

        return generation_config, contents

    def call(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make a synchronous API call to the Google language model."""
        start_time = time.time()

        # Get parameters for the API call
        generation_config, contents = self._prepare_call_params(prompt, system_message, response_format)

        try:
            # Initialize Gemini model
            model = aiplatform.GenerativeModel(model_name=self.model)

            # Send the request
            log(f"Sending request to Google Gemini API...")
            response = model.generate_content(
                contents,
                generation_config=generation_config
            )

            response_time = time.time() - start_time
            log(f"API response received in {response_time:.2f} seconds")

            return response.text

        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling Google API with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling Google API: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            time.sleep(2)  # Wait before retrying
            return self.call(prompt, system_message, response_format, max_retries - 1)

    async def call_async(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make an asynchronous API call to the Google language model."""
        start_time = time.time()

        # Get parameters for the API call
        generation_config, contents = self._prepare_call_params(prompt, system_message, response_format)

        try:
            # Initialize Gemini model
            model = aiplatform.GenerativeModel(model_name=self.model)

            # Define an async function that wraps the synchronous API call
            async def async_generate():
                # Run the synchronous API in a thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: model.generate_content(contents, generation_config=generation_config)
                )

            # Send the request asynchronously
            log(f"Sending async request to Google Gemini API...")
            response = await async_generate()

            response_time = time.time() - start_time
            log(f"Async API response received in {response_time:.2f} seconds")

            return response.text

        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling Google API async with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling Google API async: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            await asyncio.sleep(2)  # Wait before retrying
            return await self.call_async(prompt, system_message, response_format, max_retries - 1)

    def parse_json_response(self, response):
        """Parse a JSON response from the LLM."""
        if not response:
            return None

        try:
            # Try to find JSON in the response
            # First try to parse the entire response
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # If that fails, try to find JSON blocks
                import re
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
                if json_match:
                    return json.loads(json_match.group(1))

                # If no code blocks, try to find anything that looks like JSON
                json_match = re.search(r'(\{[\s\S]*\})', response)
                if json_match:
                    return json.loads(json_match.group(1))

                # If all else fails
                log(f"Could not extract JSON from response", level="ERROR")
                log(f"Response was: {response[:500]}...", level="ERROR")
                return None
        except Exception as e:
            log(f"Error parsing JSON response: {e}", level="ERROR")
            log(f"Response was: {response[:500]}...", level="ERROR")
            return None
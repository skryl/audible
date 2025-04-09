"""
OpenAI LLM provider implementation.
"""

import json
import time
import asyncio
from openai import OpenAI, AsyncOpenAI
from audible.utils.common import log, get_token_count, truncate_to_token_limit

class OpenAILLM:
    """Class for interacting with OpenAI language models."""

    def __init__(self, model="o3-mini", temperature=0.0):
        """Initialize OpenAI LLM provider."""
        self.model = model
        self.temperature = temperature
        self.client = OpenAI()  # Assumes API key is in environment variable OPENAI_API_KEY
        self.async_client = AsyncOpenAI()  # Async client

    def get_token_limit(self):
        """Get the token limit for the current model."""
        model_limits = {
            "gpt-4o": 200000,
            "gpt-4-turbo": 128000,
            "gpt-4": 8192,
            "gpt-3.5-turbo": 16385,
            "o3-mini": 200000,
            "o3-preview": 200000,
            "o3-opus": 200000
        }
        return model_limits.get(self.model, 8192)  # Default to 8192 if model not found

    def _prepare_call_params(self, prompt, system_message=None, response_format=None):
        """Prepare parameters for API calls (both sync and async)."""
        log(f"Preparing API call to OpenAI model {self.model}")

        # Calculate total tokens and handle token limits
        token_limit = self.get_token_limit()

        # Reserve tokens for system message and response
        system_tokens = get_token_count(system_message) if system_message else 0
        reserved_tokens = system_tokens + 3000  # Reserve ~3000 tokens for response

        # Calculate available tokens for prompt
        available_tokens = token_limit - reserved_tokens

        # Truncate prompt if needed
        prompt_tokens = get_token_count(prompt)
        if prompt_tokens > available_tokens:
            log(f"Prompt too long ({prompt_tokens} tokens), truncating to fit within limit ({available_tokens} tokens)", level="WARNING")
            prompt = truncate_to_token_limit(prompt, available_tokens)

        # Build messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        # Log token usage
        total_tokens = system_tokens + get_token_count(prompt)
        log(f"Using {total_tokens} tokens for API call (limit: {token_limit})")

        # Set up the kwargs dict based on the model
        kwargs = {
            "model": self.model,
            "messages": messages,
        }

        # Only add temperature for models that support it
        if not self.model.startswith("o3-"):
            kwargs["temperature"] = self.temperature

        if response_format:
            kwargs["response_format"] = response_format

        return kwargs

    def call(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make a synchronous API call to the OpenAI language model."""
        start_time = time.time()

        # Get parameters for the API call
        kwargs = self._prepare_call_params(prompt, system_message, response_format)

        log(f"Sending request to OpenAI API...")

        # Try initial request
        try:
            response = self.client.chat.completions.create(**kwargs)
            response_time = time.time() - start_time
            log(f"API response received in {response_time:.2f} seconds")
            return response.choices[0].message.content
        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling OpenAI API with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling OpenAI API: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            time.sleep(2)  # Wait before retrying
            return self.call(prompt, system_message, response_format, max_retries - 1)

    async def call_async(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make an asynchronous API call to the OpenAI language model."""
        start_time = time.time()

        # Get parameters for the API call
        kwargs = self._prepare_call_params(prompt, system_message, response_format)

        log(f"Sending async request to OpenAI API...")

        # Try initial request
        try:
            response = await self.async_client.chat.completions.create(**kwargs)
            response_time = time.time() - start_time
            log(f"Async API response received in {response_time:.2f} seconds")
            return response.choices[0].message.content
        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling OpenAI API async with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling OpenAI API async: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            await asyncio.sleep(2)  # Wait before retrying
            return await self.call_async(prompt, system_message, response_format, max_retries - 1)

    def parse_json_response(self, response):
        """Parse a JSON response from the LLM."""
        if not response:
            return None

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            log(f"Error parsing JSON response: {e}", level="ERROR")
            log(f"Response was: {response[:500]}...", level="ERROR")
            return None
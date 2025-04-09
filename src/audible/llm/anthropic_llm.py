"""
Anthropic LLM provider implementation.
"""

import json
import time
import asyncio
import anthropic
from audible.utils.common import log, get_token_count, truncate_to_token_limit

class AnthropicLLM:
    """Class for interacting with Anthropic language models."""

    def __init__(self, model="claude-3-opus-20240229", temperature=0.0):
        """Initialize Anthropic LLM provider."""
        self.model = model
        self.temperature = temperature
        self.client = anthropic.Anthropic()  # Assumes API key is in environment variable ANTHROPIC_API_KEY
        self.async_client = anthropic.AsyncAnthropic()  # Async client

    def get_token_limit(self):
        """Get the token limit for the current model."""
        model_limits = {
            "claude-3-opus-20240229": 200000,
            "claude-3-sonnet-20240229": 180000,
            "claude-3-haiku-20240307": 150000,
            "claude-2.1": 200000,
            "claude-2.0": 100000,
        }
        return model_limits.get(self.model, 100000)  # Default to 100000 if model not found

    def _prepare_call_params(self, prompt, system_message=None, response_format=None):
        """Prepare parameters for API calls (both sync and async)."""
        log(f"Preparing API call to Anthropic model {self.model}")

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

        # Set up the kwargs dict based on the model
        kwargs = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": 4000,  # Can be adjusted based on expected response size
        }

        # Add messages
        if system_message:
            kwargs["system"] = system_message

        kwargs["messages"] = [{"role": "user", "content": prompt}]

        # Handle response format (for JSON responses)
        if response_format and response_format.get("type") == "json_object":
            # Add structured output instruction
            if system_message:
                kwargs["system"] = system_message + "\nYou must respond with valid JSON."
            else:
                kwargs["system"] = "You must respond with valid JSON."

        # Log token usage
        total_tokens = system_tokens + get_token_count(prompt)
        log(f"Using {total_tokens} tokens for API call (limit: {token_limit})")

        return kwargs

    def call(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make a synchronous API call to the Anthropic language model."""
        start_time = time.time()

        # Get parameters for the API call
        kwargs = self._prepare_call_params(prompt, system_message, response_format)

        log(f"Sending request to Anthropic API...")

        # Try initial request
        try:
            response = self.client.messages.create(**kwargs)
            response_time = time.time() - start_time
            log(f"API response received in {response_time:.2f} seconds")
            return response.content[0].text
        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling Anthropic API with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling Anthropic API: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            time.sleep(2)  # Wait before retrying
            return self.call(prompt, system_message, response_format, max_retries - 1)

    async def call_async(self, prompt, system_message=None, response_format=None, max_retries=1):
        """Make an asynchronous API call to the Anthropic language model."""
        start_time = time.time()

        # Get parameters for the API call
        kwargs = self._prepare_call_params(prompt, system_message, response_format)

        log(f"Sending async request to Anthropic API...")

        # Try initial request
        try:
            response = await self.async_client.messages.create(**kwargs)
            response_time = time.time() - start_time
            log(f"Async API response received in {response_time:.2f} seconds")
            return response.content[0].text
        except Exception as e:
            if max_retries <= 0:
                log(f"Error calling Anthropic API async with no retries left: {e}", level="ERROR")
                return None

            log(f"Error calling Anthropic API async: {e}", level="ERROR")
            log(f"Waiting 2 seconds before retrying... ({max_retries} retries left)", level="INFO")
            await asyncio.sleep(2)  # Wait before retrying
            return await self.call_async(prompt, system_message, response_format, max_retries - 1)

    def parse_json_response(self, response):
        """Parse a JSON response from the LLM."""
        if not response:
            return None

        try:
            # Try to find JSON in the response (Claude sometimes adds explanations)
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
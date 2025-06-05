"""
AI module for interacting with language models.
"""

import json
import time
import os
import asyncio
from typing import Dict, Any, Optional, Union

from audible.utils.common import log, get_token_count, truncate_to_token_limit, get_prompt
from audible.llm.llm_factory import LLMFactory

# Get the default LLM provider from environment variables or use OpenAI
DEFAULT_LLM_PROVIDER = os.getenv("AUDIBLE_LLM_PROVIDER", "openai").lower()
DEFAULT_LLM_MODEL = os.getenv("AUDIBLE_LLM_MODEL", None)  # None will use the provider's default
USE_ASYNC = os.getenv("AUDIBLE_USE_ASYNC", "false").lower() == "true"

def call_llm_api(prompt, system_message=None, model=None, temperature=0.0,
                response_format=None, provider=None, use_async=None):
    """
    Make an API call to a language model.

    Args:
        prompt: The prompt to send to the model
        system_message: Optional system message to include
        model: The model to use (provider-specific)
        temperature: Temperature for generation (0.0-1.0)
        response_format: Format for the response (provider-specific)
        provider: LLM provider to use (openai, anthropic, etc.)
        use_async: Whether to use async processing (defaults to env variable)

    Returns:
        The model's response text
    """
    # Use environment variables or defaults if not specified
    provider = provider or DEFAULT_LLM_PROVIDER

    # Check if async should be used
    if use_async is None:
        use_async = os.getenv("AUDIBLE_USE_ASYNC", "false").lower() == "true"

    # If async is requested, use async call via event loop
    if use_async:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            call_llm_api_async(prompt, system_message, model, temperature, response_format, provider)
        )

    # Otherwise use synchronous call
    # If model is None, the factory will use the provider's default model
    llm = LLMFactory.create(provider=provider, model=model, temperature=temperature)

    # Call the appropriate provider
    return llm.call(prompt, system_message, response_format)

async def call_llm_api_async(prompt, system_message=None, model=None, temperature=0.0,
                          response_format=None, provider=None):
    """
    Make an asynchronous API call to a language model.

    Args:
        prompt: The prompt to send to the model
        system_message: Optional system message to include
        model: The model to use (provider-specific)
        temperature: Temperature for generation (0.0-1.0)
        response_format: Format for the response (provider-specific)
        provider: LLM provider to use (openai, anthropic, etc.)

    Returns:
        The model's response text
    """
    # Use environment variables or defaults if not specified
    provider = provider or DEFAULT_LLM_PROVIDER

    # If model is None, the factory will use the provider's default model
    llm = LLMFactory.create(provider=provider, model=model, temperature=temperature)

    # If the LLM provider has async support, use it
    if hasattr(llm, 'call_async') and callable(llm.call_async):
        return await llm.call_async(prompt, system_message, response_format)

    # Otherwise, run the synchronous call in a thread
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: llm.call(prompt, system_message, response_format)
    )

async def batch_llm_calls_async(prompts, system_messages=None, model=None, temperature=0.0,
                            response_format=None, provider=None):
    """
    Make multiple asynchronous LLM API calls in parallel.

    Args:
        prompts: List of prompts to send
        system_messages: List of system messages (or single one to use for all)
        model: The model to use
        temperature: Temperature for generation
        response_format: Format for responses
        provider: LLM provider to use

    Returns:
        List of model responses in the same order as prompts
    """
    if system_messages is None:
        system_messages = [None] * len(prompts)
    elif not isinstance(system_messages, list):
        # If a single system message is provided, use it for all prompts
        system_messages = [system_messages] * len(prompts)

    # Ensure we have the same number of prompts and system messages
    assert len(prompts) == len(system_messages), "Number of prompts and system messages must match"

    # Create tasks for all API calls
    tasks = [
        call_llm_api_async(
            prompt,
            system_message,
            model,
            temperature,
            response_format,
            provider
        )
        for prompt, system_message in zip(prompts, system_messages)
    ]

    # Wait for all tasks to complete
    return await asyncio.gather(*tasks)

def batch_llm_calls(prompts, system_messages=None, model=None, temperature=0.0,
                  response_format=None, provider=None):
    """
    Make multiple LLM API calls in parallel (synchronous wrapper around async version).

    Args:
        prompts: List of prompts to send
        system_messages: List of system messages (or single one to use for all)
        model: The model to use
        temperature: Temperature for generation
        response_format: Format for responses
        provider: LLM provider to use

    Returns:
        List of model responses in the same order as prompts
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there is no event loop in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        batch_llm_calls_async(
            prompts,
            system_messages,
            model,
            temperature,
            response_format,
            provider
        )
    )
"""
Thread pool utility for concurrent LLM API requests.

This module provides functionality for making multiple LLM API calls concurrently.
"""

import asyncio
import concurrent.futures
from functools import partial
import os
import threading
from typing import Callable, List, Any, Dict, Union, Optional, Tuple

from audible.utils.common import log

# Maximum number of concurrent requests
MAX_CONCURRENT_REQUESTS = 5

# Thread-local storage for managing thread-specific data
_thread_local = threading.local()

# Global executor for thread pool
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)

# Global asyncio semaphore for limiting concurrent async tasks
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def set_max_concurrent_requests(max_requests: int):
    """Set the maximum number of concurrent requests."""
    global MAX_CONCURRENT_REQUESTS, _executor, _semaphore

    # Don't allow fewer than 1 or more than 20 concurrent requests
    max_requests = max(1, min(20, max_requests))

    if max_requests != MAX_CONCURRENT_REQUESTS:
        MAX_CONCURRENT_REQUESTS = max_requests

        # Shut down the existing executor and create a new one
        _executor.shutdown(wait=False)
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)

        # Create a new semaphore
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        log(f"Set maximum concurrent requests to {MAX_CONCURRENT_REQUESTS}")


def run_in_thread_pool(fn: Callable, *args, **kwargs) -> Any:
    """
    Run a function in the thread pool.

    Args:
        fn: The function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function
    """
    return _executor.submit(fn, *args, **kwargs).result()


def process_in_parallel(items: List[Any], process_fn: Callable, max_workers: Optional[int] = None) -> List[Any]:
    """
    Process a list of items in parallel using the thread pool.

    Args:
        items: List of items to process
        process_fn: Function to process each item
        max_workers: Maximum number of workers (defaults to MAX_CONCURRENT_REQUESTS)

    Returns:
        List of results from processing each item
    """
    max_workers = max_workers or MAX_CONCURRENT_REQUESTS

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_fn, item) for item in items]
        return [future.result() for future in concurrent.futures.as_completed(futures)]


async def process_async(fn: Callable, *args, **kwargs) -> Any:
    """
    Process a function asynchronously with semaphore limiting.

    Args:
        fn: The function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function
    """
    async with _semaphore:
        # If the function is a coroutine function, await it directly
        if asyncio.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)

        # Otherwise, run it in the executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, partial(fn, *args, **kwargs))


async def process_all_async(items: List[Any], process_fn: Callable) -> List[Any]:
    """
    Process all items asynchronously with concurrency limits.

    Args:
        items: List of items to process
        process_fn: Function to process each item (can be sync or async)

    Returns:
        List of results in the same order as the input items
    """
    tasks = [process_async(process_fn, item) for item in items]
    return await asyncio.gather(*tasks)


def run_async_tasks(coro) -> Any:
    """
    Run an async coroutine from synchronous code.

    Args:
        coro: The coroutine to run

    Returns:
        The result of the coroutine
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If there is no event loop in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


def process_batch_async(items: List[Any], process_fn: Callable) -> List[Any]:
    """
    Process a batch of items asynchronously from synchronous code.

    Args:
        items: List of items to process
        process_fn: Function to process each item (can be sync or async)

    Returns:
        List of results in the same order as the input items
    """
    return run_async_tasks(process_all_async(items, process_fn))
"""Utility functions for API calls with retry logic and error handling."""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from openai import APIError, APITimeoutError, RateLimitError

T = TypeVar("T")


def retry_with_exponential_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry API calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        exponential_base: Base for exponential backoff calculation
        max_delay: Maximum delay between retries in seconds
    
    Usage:
        @retry_with_exponential_backoff(max_retries=3)
        def call_api():
            return client.embeddings.create(...)
    """
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (APITimeoutError, RateLimitError, APIError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    # Calculate next delay with exponential backoff
                    wait_time = min(delay * (exponential_base ** attempt), max_delay)
                    print(f"[retry] Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                except Exception as e:
                    # Don't retry on unexpected errors - re-raise immediately
                    raise e
            
            # All retries exhausted
            if last_exception:
                raise last_exception
            raise Exception(f"Max retries exceeded for {func.__name__}")
        
        return wrapper
    
    return decorator


async def retry_with_exponential_backoff_async(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Async version of retry with exponential backoff.
    
    Usage:
        result = await retry_with_exponential_backoff_async(
            client.embeddings.create,
            model="text-embedding-3-large",
            input=["text"]
        )
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
        except (APITimeoutError, RateLimitError, APIError) as e:
            last_exception = e
            if attempt == max_retries:
                break
            
            wait_time = min(delay * (exponential_base ** attempt), max_delay)
            print(f"[retry] Attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)
        except Exception:
            raise
    
    if last_exception:
        raise last_exception
    raise Exception(f"Max retries exceeded for async call")


def validate_file_content(file_path: str, content: str) -> tuple[bool, str]:
    """
    Validate file content for processing.
    
    Args:
        file_path: Path to the file
        content: File content as string
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if content is empty
    if not content or not content.strip():
        return False, f"File {file_path} is empty or contains only whitespace"
    
    # Check minimum length (at least 10 characters of actual content)
    if len(content.strip()) < 10:
        return False, f"File {file_path} is too short (less than 10 characters)"
    
    # Check for corrupted/binary content (high ratio of non-printable characters)
    printable_chars = sum(1 for c in content if c.isprintable() or c.isspace())
    total_chars = len(content)
    if total_chars > 0:
        printable_ratio = printable_chars / total_chars
        if printable_ratio < 0.8:  # More than 20% non-printable
            return False, f"File {file_path} appears to be corrupted or binary (only {printable_ratio:.1%} printable)"
    
    return True, ""

import os
import time

from dotenv import load_dotenv
from openai import OpenAI
from openai._exceptions import APIConnectionError

load_dotenv()

RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BASE_WAIT_SECONDS = 2


def make_client() -> OpenAI:
    """Build te client from .env. max_retries=0: we do the retrying ourselves."""
    return OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        max_retries=0,
        timeout=90
    )


def is_retryable(error: Exception) -> bool:
    """True for a busy line(rate limit, server error, network). False for our own mistakes."""
    if isinstance(error, APIConnectionError):
        return True
    return getattr(error, "status_code", None) in RETRY_STATUS


def call_model(prompt: str, client=None, sleep=time.sleep) -> dict:
    """Send one prompt. Retry busy-line errors with backoff. Return the reply text, tokens in, tokens out, and seconds, and attempts."""
    client = client or make_client()

    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as error:
            if attempt == MAX_ATTEMPTS or not is_retryable(error):
                raise
            wait = BASE_WAIT_SECONDS * 2 ** (attempt - 1)
            print(f"call failed ({type(error).__name__}), retry {attempt} in {wait}s")
            sleep(wait)
            continue
        
        seconds = time.perf_counter() - start
        usage = response.usage
        return{
            "text":response.choices[0].message.content or "",
            "tokens_in": usage.prompt_tokens if usage else 0,
            "tokens_out": usage.completion_tokens if usage else 0,
            "seconds": seconds,
            "attempts": attempt,
        }

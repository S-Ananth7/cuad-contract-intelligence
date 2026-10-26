import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def call_model(prompt: str) -> dict:
    """Send one prompt. Return the reply text, tokens in, tokens out, and seconds."""
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        timeout=180,
    )

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    seconds = time.perf_counter() - start

    text = response.choices[0].message.content or ""
    usage = response.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0

    return {
        "text": text,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "seconds": seconds,
    }
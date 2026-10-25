import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def call_model(prompt: str) -> str:
    """Send one prompt, return the reply text plus tokens in, tokens out, and seconds."""
    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
    )

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    seconds = time.perf_counter() - start

    return {
        "text": response.choices[0].message.content,
        "tokens_in": response.usage.prompt_tokens,
        "tokens_out": response.usage.completion_tokens,
        "seconds": seconds,
    }

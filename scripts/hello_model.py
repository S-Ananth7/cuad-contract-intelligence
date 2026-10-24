import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"],
    max_retries=0,
)

response = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    max_tokens=500,
    messages=[{"role": "user", "content": "Say hello in five words."}],
)

print(response.choices[0].message.content)
print(response.usage.prompt_tokens, response.usage.completion_tokens)

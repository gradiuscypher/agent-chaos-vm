from openai import AsyncOpenAI
from ..utils.config import config
import asyncio
import random


class Brain:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
        )
        self.total_tokens = 0
        self.last_context_tokens = 0

    async def think(
        self, system_prompt: str, messages: list, max_retries: int = 5
    ) -> str:
        retries = 0
        while retries < max_retries:
            try:
                response = await self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://github.com/agent-chaos",
                        "X-Title": "Agent Chaos",
                    },
                    model=config.GEMINI_MODEL,
                    messages=[{"role": "system", "content": system_prompt}, *messages],
                )

                # Token tracking
                usage = response.usage
                if usage:
                    self.total_tokens += usage.total_tokens
                    self.last_context_tokens = (
                        usage.prompt_tokens + usage.completion_tokens
                    )

                return response.choices[0].message.content or ""
            except Exception as e:
                if "429" in str(e):
                    retries += 1
                    wait_time = (2**retries) + random.random()
                    print(
                        f"DEBUG: Rate limited (429). Retrying in {wait_time:.2f}s... (Attempt {retries}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return "ERROR: Max retries exceeded for OpenRouter request."

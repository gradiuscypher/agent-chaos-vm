from openai import AsyncOpenAI
from ..utils.config import config


class Brain:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
        )

    async def think(self, system_prompt: str, messages: list) -> str:
        try:
            response = await self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/agent-chaos",
                    "X-Title": "Agent Chaos",
                },
                model=config.GEMINI_MODEL,
                messages=[{"role": "system", "content": system_prompt}, *messages],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise e

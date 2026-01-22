import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List

load_dotenv(override=True)


class Config(BaseModel):
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    VM_IPS: List[str] = os.getenv("VM_IPS", "").split(",")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "google/gemini-3-flash-preview")
    ALLOWED_USER_IDS: List[int] = [
        int(uid) for uid in os.getenv("ALLOWED_USER_IDS", "").split(",") if uid
    ]
    EXCLUDED_CHANNEL_ID: int = int(os.getenv("EXCLUDED_CHANNEL_ID", "0"))
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    UPDATE_CHANNEL_ID: int = int(os.getenv("UPDATE_CHANNEL_ID", "0"))
    UPDATE_THREAD_ID: int = int(os.getenv("UPDATE_THREAD_ID", "0"))


config = Config()

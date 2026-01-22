import discord
import json
import os
from datetime import datetime, timedelta, timezone
from typing import List
from ..utils.config import config


class DiscordScraper(discord.Client):
    def __init__(self, target_user_ids: List[int], excluded_channel_id: int):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.target_user_ids = target_user_ids
        self.excluded_channel_id = excluded_channel_id
        self.data = {uid: [] for uid in target_user_ids}

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        sixty_days_ago = datetime.now(timezone.utc) - timedelta(days=60)

        os.makedirs("data/logs", exist_ok=True)

        for guild in self.guilds:
            print(f"Processing guild: {guild.name}")
            for channel in guild.text_channels:
                if channel.id == self.excluded_channel_id:
                    continue

                # Basic check to see if the channel has had activity in the last 60 days
                # This is a heuristic: if the last message is older than 60 days, we skip.
                if channel.last_message_id:
                    last_msg_time = discord.utils.snowflake_time(
                        channel.last_message_id
                    )
                    if last_msg_time < sixty_days_ago:
                        print(f"Skipping inactive channel: {channel.name}")
                        continue

                try:
                    print(f"Scraping channel: {channel.name}")
                    async for message in channel.history(
                        limit=None, after=sixty_days_ago
                    ):
                        if message.author.id in self.target_user_ids:
                            self.data[message.author.id].append(
                                {
                                    "content": message.content,
                                    "timestamp": message.created_at.isoformat(),
                                    "channel_id": message.channel.id,
                                }
                            )

                    # Periodic save to avoid loss of progress
                    self.save_logs()
                except discord.Forbidden:
                    print(f"Permission denied for channel: {channel.name}")
                except Exception as e:
                    print(f"Error scraping {channel.name}: {e}")

        print("Scraping complete. Shutting down...")
        self.save_logs()
        await self.close()

    def save_logs(self):
        for uid, messages in self.data.items():
            if messages:
                # Merge with existing logs if any
                filepath = f"data/logs/{uid}.json"
                existing_data = []
                if os.path.exists(filepath):
                    try:
                        with open(filepath, "r") as f:
                            existing_data = json.load(f)
                    except:
                        pass

                # Simple de-duplication based on timestamp and content
                # This isn't perfect but helps for incremental scrapes
                seen = set()
                combined = []
                for msg in existing_data + messages:
                    key = (msg["timestamp"], msg["content"])
                    if key not in seen:
                        combined.append(msg)
                        seen.add(key)

                with open(filepath, "w") as f:
                    json.dump(combined, f, indent=4)


def run_scraper(token: str):
    scraper = DiscordScraper(config.ALLOWED_USER_IDS, config.EXCLUDED_CHANNEL_ID)
    scraper.run(token)

import discord
import asyncio
from typing import Optional
from ..utils.config import config


class DiscordBridge:
    def __init__(self, token: str):
        self.token = token
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self.is_ready = False
        self._loop_task = None

    async def start(self):
        self._loop_task = asyncio.create_task(self.client.start(self.token))
        while not self.client.is_ready():
            await asyncio.sleep(1)
        self.is_ready = True
        print("Discord Bridge ready.")

    async def get_user_info(self, user_id: int) -> tuple[str, Optional[str]]:
        if not self.is_ready:
            return str(user_id), None
        try:
            user = await self.client.fetch_user(user_id)
            avatar_url = str(user.display_avatar.url) if user.display_avatar else None
            return user.name, avatar_url
        except:
            return str(user_id), None

    async def send_update(
        self,
        content: str,
        sender_name: Optional[str] = None,
        thread_id: Optional[int] = None,
        color: int = 0x3498DB,  # Default Blue
        avatar_url: Optional[str] = None,
    ):
        if not self.is_ready:
            return

        display_name = sender_name or "Unknown Agent"

        embed = discord.Embed(
            title=f"Update from {display_name}",
            description=content,
            color=color,
            timestamp=discord.utils.utcnow(),
        )
        if avatar_url:
            embed.set_footer(text="Agent Chaos Autonomy Protocol", icon_url=avatar_url)
        else:
            embed.set_footer(text="Agent Chaos Autonomy Protocol")

        target_id = thread_id or config.UPDATE_THREAD_ID
        channel = self.client.get_channel(target_id)
        if channel and isinstance(channel, (discord.Thread, discord.TextChannel)):
            await channel.send(embed=embed)
        else:
            # Try to fetch if not in cache
            try:
                channel = await self.client.fetch_channel(target_id)
                if isinstance(channel, (discord.Thread, discord.TextChannel)):
                    await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send Discord update: {e}")

    async def send_service_summary(
        self, services: list, thread_id: Optional[int] = None
    ):
        if not self.is_ready or not services:
            return

        embed = discord.Embed(
            title="🛰️ Active Services Status Report",
            color=0x2ECC71,  # Green
            timestamp=discord.utils.utcnow(),
        )

        from datetime import datetime

        for svc in services:
            uptime_str = "Unknown"
            if svc.start_time:
                try:
                    start_time = datetime.fromisoformat(
                        svc.start_time.replace(" ", "T")
                    )
                    uptime = datetime.now() - start_time
                    uptime_str = str(uptime).split(".")[0]
                except:
                    pass

            value = (
                f"**Host:** `{svc.vm_ip}`\n"
                f"**Agent:** `{svc.agent_id}`\n"
                f"**Uptime:** `{uptime_str}`\n"
                f"**Reason:** {svc.description}"
            )
            embed.add_field(name=f"🔹 {svc.service_name}", value=value, inline=False)

        embed.set_footer(text="Agent Chaos Autonomy Protocol • Next update in 60s")

        target_id = thread_id or config.UPDATE_THREAD_ID
        channel = self.client.get_channel(target_id)
        if not channel:
            try:
                channel = await self.client.fetch_channel(target_id)
            except:
                pass

        if channel and isinstance(channel, (discord.Thread, discord.TextChannel)):
            await channel.send(embed=embed)

    async def stop(self):
        await self.client.close()
        if self._loop_task:
            self._loop_task.cancel()

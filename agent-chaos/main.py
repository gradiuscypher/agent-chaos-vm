import asyncio
import sys
import os
from src.utils.scraper import run_scraper
from src.agents.agent import Agent
from src.communication.agora import Agora
from src.utils.config import config
from src.bridge.discord import DiscordBridge
from src.utils.monitor import run_monitor
from src.utils.service_monitor import run_service_monitor
from src.utils.interact import run_interrogator


async def service_report_loop(agora: Agora, discord_bridge: DiscordBridge):
    while True:
        await asyncio.sleep(60)
        try:
            services = await agora.get_services()
            if services:
                await discord_bridge.send_service_summary(services)
        except Exception as e:
            print(f"Error in service report loop: {e}")


async def start_agents():
    agora = Agora()
    await agora.initialize()

    discord_bridge = DiscordBridge(config.DISCORD_BOT_TOKEN)
    await discord_bridge.start()

    # Identify available log files to determine which agents to start
    agents = []
    log_files = os.listdir("data/logs") if os.path.exists("data/logs") else []

    for filename in log_files:
        if filename.endswith(".json"):
            try:
                user_id = int(filename.split(".")[0])
                if user_id in config.ALLOWED_USER_IDS:
                    print(f"Starting agent for user {user_id}")
                    agent = Agent(user_id, agora, discord_bridge)
                    agents.append(agent.run())
            except ValueError:
                continue

    if not agents:
        print(
            "No agent logs found in data/logs/. Please run with 'scrape' first or provide DISCORD_BOT_TOKEN."
        )
        return

    # Run agents, monitor, and service report concurrently
    await asyncio.gather(
        *agents, run_monitor(), service_report_loop(agora, discord_bridge)
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [scrape|run]")
        return

    mode = sys.argv[1]

    if mode == "scrape":
        token = config.DISCORD_BOT_TOKEN
        if not token:
            print("Please set DISCORD_BOT_TOKEN in .env")
            return
        run_scraper(token)
    elif mode == "run":
        asyncio.run(start_agents())
    elif mode == "services":
        asyncio.run(run_service_monitor())
    elif mode == "interact":
        asyncio.run(run_interrogator())
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()

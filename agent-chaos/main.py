import asyncio
import sys
import os
import subprocess
import signal
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


async def start_single_agent(user_id: int):
    agora = Agora()
    await agora.initialize()

    discord_bridge = DiscordBridge(config.DISCORD_BOT_TOKEN)
    await discord_bridge.start()

    agent = Agent(user_id, agora, discord_bridge)
    await agent.run()


async def start_agents_orchestrator():
    agora = Agora()
    await agora.initialize()

    discord_bridge = DiscordBridge(config.DISCORD_BOT_TOKEN)
    await discord_bridge.start()

    # Identify available log files
    log_files = os.listdir("data/logs") if os.path.exists("data/logs") else []

    active_user_ids = []
    for filename in log_files:
        if filename.endswith(".json"):
            try:
                user_id = int(filename.split(".")[0])
                if user_id in config.ALLOWED_USER_IDS:
                    active_user_ids.append(user_id)
            except ValueError:
                continue

    if not active_user_ids:
        print("No agent logs found. Run 'scrape' first.")
        return

    # Start report loop and monitor
    await asyncio.gather(service_report_loop(agora, discord_bridge), run_monitor())


def spawn_background_agents():
    log_files = os.listdir("data/logs") if os.path.exists("data/logs") else []
    for filename in log_files:
        if filename.endswith(".json"):
            user_id = filename.split(".")[0]
            if int(user_id) in config.ALLOWED_USER_IDS:
                print(f"Spawning agent for user {user_id} in background...")
                subprocess.Popen(
                    [sys.executable, "main.py", "agent", user_id],
                    stdout=open(f"data/state/agent_{user_id}.log", "a"),
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setpgrp,
                )


async def stop_all_agents():
    agora = Agora()
    await agora.initialize()
    registry = await agora.get_registry()
    for entry in registry:
        if entry.status == "active":
            print(f"Stopping agent {entry.agent_id} (PID {entry.pid})...")
            try:
                os.kill(entry.pid, signal.SIGTERM)
            except ProcessLookupError:
                print(f"Process {entry.pid} already gone.")
    print("All active agents signaled to stop.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py [scrape|run|services|interact|stop|agent <uid>]")
        return

    mode = sys.argv[1]

    if mode == "scrape":
        token = config.DISCORD_BOT_TOKEN
        if not token:
            print("Please set DISCORD_BOT_TOKEN in .env")
            return
        run_scraper(token)
    elif mode == "run":
        spawn_background_agents()
        asyncio.run(start_agents_orchestrator())
    elif mode == "agent":
        user_id = int(sys.argv[2])
        asyncio.run(start_single_agent(user_id))
    elif mode == "services":
        asyncio.run(run_service_monitor())
    elif mode == "interact":
        asyncio.run(run_interrogator())
    elif mode == "stop":
        asyncio.run(stop_all_agents())
    else:
        print(f"Unknown mode: {mode}")


if __name__ == "__main__":
    main()

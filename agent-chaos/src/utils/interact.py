import asyncio
import os
import json
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.syntax import Syntax
from ..communication.agora import Agora

console = Console()


async def listen_for_responses(agora: Agora, show_internal: bool = False):
    last_processed_id = 0
    recent = await agora.get_recent(limit=1)
    if recent and recent[0].id is not None:
        last_processed_id = recent[0].id

    while True:
        await asyncio.sleep(2)
        # Fetch NEW messages
        messages = await agora.get_recent(limit=50, after_id=last_processed_id)

        for msg in messages:
            if msg.id is not None and msg.id > last_processed_id:
                if msg.type == "operator_response":
                    console.print(
                        f"\n[bold green]>>> Response from {msg.agent_id}:[/bold green]"
                    )
                    console.print(Panel(msg.content, border_style="green"))
                elif show_internal and msg.type in ["thought", "feeling"]:
                    color = "yellow" if msg.type == "thought" else "red"
                    console.print(
                        f"\n[dim {color}]({msg.agent_id} {msg.type}): {msg.content}[/]"
                    )

                last_processed_id = msg.id


async def run_interrogator():
    agora = Agora()
    await agora.initialize()

    console.print("[bold red]Agent Chaos - Master Interrogation & Control[/bold red]")

    show_internal = (
        Prompt.ask(
            "Show internal thoughts/feelings in real-time?",
            choices=["y", "n"],
            default="n",
        )
        == "y"
    )
    asyncio.create_task(listen_for_responses(agora, show_internal))

    while True:
        # Get active agents from registry
        registry = await agora.get_registry()
        active_agents = [e.agent_id for e in registry if e.status == "active"]

        options = [
            "all",
            "[Logs]",
            "[Profiles]",
            "[Stop All]",
            "[Stop Agent]",
            "[Exit]",
        ] + active_agents
        choice = Prompt.ask("Target", choices=options, default="all")

        if choice == "[Exit]":
            break
        elif choice == "[Stop All]":
            await agora.post("system", "STOP", "command")
            console.print("[bold red]Stop signal sent to all agents.[/bold red]")
            continue
        elif choice == "[Stop Agent]":
            agent_to_stop = Prompt.ask("Which agent?", choices=active_agents)
            await agora.post(agent_to_stop, "STOP", "command")
            console.print(f"[bold red]Stop signal sent to {agent_to_stop}.[/bold red]")
            continue
        elif choice == "[Logs]":
            log_files = [f for f in os.listdir("data/logs") if f.endswith(".json")]
            if not log_files:
                console.print("No logs found.")
                continue
            log_choice = Prompt.ask("Which user log?", choices=log_files)
            with open(f"data/logs/{log_choice}", "r") as f:
                data = json.load(f)
                console.print(Syntax(json.dumps(data[:10], indent=2), "json"))
                console.print(f"... showing first 10 of {len(data)} messages.")
            continue
        elif choice == "[Profiles]":
            # We'll just ask the agents to share their profiles
            await agora.post(
                "all",
                "Please state your full personality profile and current objectives.",
                "user_query",
            )
            console.print("[cyan]Requested profiles from all agents.[/cyan]")
            continue

        question = Prompt.ask(f"Message for [bold cyan]{choice}[/bold cyan]")

        if question:
            # If 'all' is selected, we post a separate query for each agent to ensure individual responses
            if choice == "all":
                for agent in active_agents:
                    await agora.post(agent, question, "user_query")
            else:
                await agora.post(choice, question, "user_query")

            console.print(f"[green]Query sent. Waiting for response...[/green]")
            console.print("-" * 20)


if __name__ == "__main__":
    asyncio.run(run_interrogator())

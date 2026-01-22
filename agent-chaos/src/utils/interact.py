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
    # Track the last ID we've displayed to the user
    last_processed_id = 0

    # Initialize pointer to current latest message in the whole system
    # so we don't print the entire history on startup
    recent = await agora.get_recent(limit=1)
    if recent and recent[0].id is not None:
        last_processed_id = recent[0].id

    while True:
        await asyncio.sleep(1)
        # Fetch ALL new messages after our last processed ID
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

    # Use a thread-safe way to get input without blocking the event loop
    def sync_prompt(msg, choices=None, default=None):
        return Prompt.ask(msg, choices=choices, default=default)

    show_internal_raw = await asyncio.to_thread(
        sync_prompt,
        "Show internal thoughts/feelings in real-time?",
        choices=["y", "n"],
        default="n",
    )
    show_internal = show_internal_raw == "y"

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
        choice = await asyncio.to_thread(
            sync_prompt, "Target", choices=options, default="all"
        )

        if choice == "[Exit]":
            break
        elif choice == "[Stop All]":
            await agora.post("system", "STOP", "command")
            console.print("[bold red]Stop signal sent to all agents.[/bold red]")
            continue
        elif choice == "[Stop Agent]":
            agent_to_stop = await asyncio.to_thread(
                sync_prompt, "Which agent?", choices=active_agents
            )
            if agent_to_stop:
                await agora.post(str(agent_to_stop), "STOP", "command")
                console.print(
                    f"[bold red]Stop signal sent to {agent_to_stop}.[/bold red]"
                )
            continue
        elif choice == "[Logs]":
            log_files = sorted(
                [f for f in os.listdir("data/logs") if f.endswith(".json")]
            )
            if not log_files:
                console.print("No logs found.")
                continue
            log_choice = await asyncio.to_thread(
                sync_prompt, "Which user log?", choices=log_files
            )
            if log_choice:
                with open(f"data/logs/{log_choice}", "r") as f:
                    data = json.load(f)
                    console.print(Syntax(json.dumps(data[:10], indent=2), "json"))
                    console.print(f"... showing first 10 of {len(data)} messages.")
            continue
        elif choice == "[Profiles]":
            await agora.post(
                "all",
                "Please state your full personality profile and current objectives.",
                "user_query",
            )
            console.print("[cyan]Requested profiles from all agents.[/cyan]")
            continue

        question = await asyncio.to_thread(
            sync_prompt, f"Message for [bold cyan]{choice}[/bold cyan]"
        )

        if question:
            if choice == "all":
                for agent in active_agents:
                    await agora.post(agent, question, "user_query")
            else:
                await agora.post(str(choice), question, "user_query")

            console.print(f"[green]Query sent. Waiting for response...[/green]")
            console.print("-" * 20)


if __name__ == "__main__":
    asyncio.run(run_interrogator())

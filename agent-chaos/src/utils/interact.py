import asyncio
from rich.console import Console
from rich.prompt import Prompt
from ..communication.agora import Agora

console = Console()


async def listen_for_responses(agora: Agora):
    # Track the last ID we've displayed to the user
    last_processed_id = 0

    # Initialize pointer to current latest message in the whole system
    # so we don't print the entire history on startup
    recent = await agora.get_recent(limit=1)
    if recent and recent[0].id is not None:
        last_processed_id = recent[0].id

    while True:
        await asyncio.sleep(2)
        # Fetch new operator responses strictly after our last processed ID
        new_messages = await agora.get_recent(
            limit=50, msg_type="operator_response", after_id=last_processed_id
        )

        for msg in new_messages:
            if msg.id is not None and msg.id > last_processed_id:
                console.print(
                    f"\n[bold green]>>> Response from {msg.agent_id}:[/bold green]"
                )
                console.print(msg.content)
                console.print("-" * 20)
                last_processed_id = msg.id

        # We also want to advance the pointer if there are NO operator responses but lots of other activity,
        # otherwise our 'get_recent' might keep scanning from an old ID.
        # But we only advance if we've checked for operator responses up to that point.
        all_latest = await agora.get_recent(limit=1)
        if all_latest and all_latest[0].id is not None:
            latest_id = all_latest[0].id
            if latest_id > last_processed_id:
                # We haven't seen an operator_response, but we know the system has moved on to latest_id.
                # However, if we just set last_processed_id = latest_id, we might skip a response
                # that was written but not yet returned by the 'operator_response' filter.
                # SQLite is consistent, so if we see ID X in the global log, it MUST be visible
                # in the filtered log too.
                last_processed_id = latest_id


async def run_interrogator():
    agora = Agora()
    await agora.initialize()

    console.print("[bold red]Agent Chaos - Interrogation Client[/bold red]")
    console.print("[dim]Responses from agents will appear here automatically.[/dim]")

    # Start listener in background
    asyncio.create_task(listen_for_responses(agora))

    while True:
        # Get active agents from recent messages
        recent = await agora.get_recent(limit=100)
        agents = sorted(
            list(set([msg.agent_id for msg in recent if msg.type != "user_query"]))
        )

        if not agents:
            console.print("[yellow]No active agents found. Waiting...[/yellow]")
            await asyncio.sleep(5)
            continue

        options = ["all"] + agents + ["[Exit]"]
        choice = Prompt.ask(
            "Which agent would you like to interrogate?", choices=options, default="all"
        )

        if choice == "[Exit]":
            break

        question = Prompt.ask(f"Enter your message for [bold cyan]{choice}[/bold cyan]")

        if question:
            await agora.post(choice, question, "user_query")
            console.print(
                f"[green]Message sent to {choice}. They will respond in their next thought cycle.[/green]"
            )
            console.print("-" * 20)


if __name__ == "__main__":
    asyncio.run(run_interrogator())

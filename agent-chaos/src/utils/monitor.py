import asyncio
from rich.console import Console
from rich.table import Table
from rich.live import Live
from ..communication.agora import Agora

console = Console()


async def run_monitor():
    agora = Agora()
    await agora.initialize()

    with Live(auto_refresh=False) as live:
        while True:
            recent = await agora.get_recent(limit=15)

            table = Table(
                title="Agent Chaos - Live Feed",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Timestamp", style="dim")
            table.add_column("Agent", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Content")

            for msg in recent:
                color = "white"
                if msg.type == "thought":
                    color = "yellow"
                elif msg.type == "feeling":
                    color = "red"
                elif msg.type == "action":
                    color = "blue"

                content = msg.content
                if len(content) > 100:
                    content = content[:97] + "..."

                table.add_row(
                    str(msg.timestamp), msg.agent_id, f"[{color}]{msg.type}[/]", content
                )

            live.update(table, refresh=True)
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_monitor())

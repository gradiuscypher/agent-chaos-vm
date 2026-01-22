import asyncio
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from ..communication.agora import Agora

console = Console()


async def run_monitor():
    agora = Agora()
    await agora.initialize()

    layout = Layout()
    layout.split_column(Layout(name="feed", ratio=2), Layout(name="stats", ratio=1))

    with Live(layout, auto_refresh=False) as live:
        while True:
            # 1. Feed Panel
            recent = await agora.get_recent(limit=15)
            feed_table = Table(
                title="Live Activity Feed",
                show_header=True,
                header_style="bold magenta",
                expand=True,
            )
            feed_table.add_column("Timestamp", style="dim")
            feed_table.add_column("Agent", style="cyan")
            feed_table.add_column("Type", style="green")
            feed_table.add_column("Content")

            for msg in recent:
                color = "white"
                if msg.type == "thought":
                    color = "yellow"
                elif msg.type == "feeling":
                    color = "red"
                elif msg.type == "action":
                    color = "blue"
                elif msg.type == "operator_response":
                    color = "bold green"

                content = msg.content
                if len(content) > 100:
                    content = content[:97] + "..."

                feed_table.add_row(
                    str(msg.timestamp), msg.agent_id, f"[{color}]{msg.type}[/]", content
                )

            layout["feed"].update(Panel(feed_table))

            # 2. Stats Panel
            registry = await agora.get_registry()
            stats_table = Table(
                title="Agent Health & Token Usage",
                show_header=True,
                header_style="bold blue",
                expand=True,
            )
            stats_table.add_column("Agent ID", style="cyan")
            stats_table.add_column("PID", style="dim")
            stats_table.add_column("Status")
            stats_table.add_column("Last Context (Tokens)", style="yellow")
            stats_table.add_column("Total Tokens", style="magenta")
            stats_table.add_column("Heartbeat", style="dim")

            for entry in registry:
                status_color = "green" if entry.status == "active" else "red"
                stats_table.add_row(
                    entry.agent_id,
                    str(entry.pid),
                    f"[{status_color}]{entry.status}[/]",
                    f"{entry.last_context_tokens:,}",
                    f"{entry.total_tokens:,}",
                    str(entry.last_heartbeat),
                )

            layout["stats"].update(Panel(stats_table))

            live.refresh()
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(run_monitor())

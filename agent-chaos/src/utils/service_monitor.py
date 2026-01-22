import asyncio
from rich.console import Console
from rich.table import Table
from rich.live import Live
from datetime import datetime
from ..communication.agora import Agora

console = Console()


async def run_service_monitor():
    agora = Agora()
    await agora.initialize()

    with Live(auto_refresh=False) as live:
        while True:
            services = await agora.get_services()

            table = Table(
                title="Agent Chaos - Active Services",
                show_header=True,
                header_style="bold green",
            )
            table.add_column("Service Name", style="cyan")
            table.add_column("VM IP", style="magenta")
            table.add_column("Agent", style="yellow")
            table.add_column("Uptime", style="blue")
            table.add_column("Status", style="bold")
            table.add_column("Description")

            for svc in services:
                # Calculate simple uptime
                uptime_str = "Unknown"
                if svc.start_time:
                    try:
                        start_time_str = str(svc.start_time).replace(" ", "T")
                        start_time = datetime.fromisoformat(start_time_str)
                        uptime = datetime.now() - start_time
                        uptime_str = str(uptime).split(".")[0]  # Remove microseconds
                    except:
                        pass

                table.add_row(
                    svc.service_name,
                    svc.vm_ip,
                    svc.agent_id,
                    uptime_str,
                    svc.status,
                    svc.description,
                )

            live.update(table, refresh=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_service_monitor())

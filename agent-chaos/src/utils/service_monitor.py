import asyncio
import re
import os
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from ..communication.agora import Agora
from ..bridge.ssh import SSHExecutor
from ..utils.config import config

console = Console()


async def get_vm_processes(ip: str):
    executor = SSHExecutor(ip)
    # This command gets ALL processes, their PIDs, command lines, and CWDs.
    # We filter for anything related to /root/chaos/
    cmd = """
    ps -eo pid,args --no-headers | while read pid args; do
        cwd=$(readlink -f /proc/$pid/cwd 2>/dev/null || echo "unknown")
        if [[ "$args" == *"/root/chaos/"* ]] || [[ "$cwd" == *"/root/chaos/"* ]]; then
            # Check if it's listening on a port
            port=$(ss -tulpn | grep "pid=$pid," | awk '{print $5}' | sed 's/.*://' | head -n 1)
            [ -z "$port" ] && port="N/A"
            echo "$pid|$port|$args|$cwd"
        fi
    done
    """
    try:
        status, stdout, stderr = await asyncio.to_thread(executor.execute, cmd)
        if status != 0:
            return []

        processes = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                processes.append(
                    {
                        "pid": parts[0],
                        "port": parts[1],
                        "command": parts[2],
                        "cwd": parts[3],
                    }
                )
        return processes
    except Exception as e:
        return []
    finally:
        executor.close()


async def run_service_monitor():
    agora = Agora()
    await agora.initialize()

    with Live(auto_refresh=False) as live:
        while True:
            registered = await agora.get_services()
            reg_map = {s.agent_id: s for s in registered}

            table = Table(
                title="[bold green]Agent Chaos - Active Process Monitor (/root/chaos/)[/bold green]",
                show_header=True,
                header_style="bold cyan",
                expand=True,
            )
            table.add_column("VM Host", style="magenta")
            table.add_column("PID", style="yellow")
            table.add_column("Port", style="bold green")
            table.add_column("Owner", style="cyan")
            table.add_column("Command / Binary", overflow="fold")
            table.add_column("CWD", style="dim", overflow="fold")

            tasks = [get_vm_processes(ip) for ip in config.VM_IPS]
            results = await asyncio.gather(*tasks)

            found_any = False
            for ip, vm_procs in zip(config.VM_IPS, results):
                for proc in vm_procs:
                    found_any = True

                    # Try to determine owner from CWD or command
                    owner = "[dim]Unknown[/dim]"
                    for agent_dir in os.listdir("data/logs"):
                        agent_name = f"chaos-{agent_dir.split('.')[0]}"
                        if agent_name in proc["cwd"] or agent_name in proc["command"]:
                            owner = agent_name
                            break

                    table.add_row(
                        ip,
                        proc["pid"],
                        proc["port"],
                        owner,
                        proc["command"],
                        proc["cwd"],
                    )

            if not found_any:
                table.add_row(
                    "-",
                    "-",
                    "-",
                    "-",
                    "[dim]No active agent processes found in /root/chaos/[/dim]",
                    "-",
                )

            live.update(table, refresh=True)
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(run_service_monitor())

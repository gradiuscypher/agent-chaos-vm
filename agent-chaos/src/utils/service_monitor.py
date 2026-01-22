import asyncio
import re
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from ..communication.agora import Agora
from ..bridge.ssh import SSHExecutor
from ..utils.config import config

console = Console()


async def get_vm_services(ip: str):
    executor = SSHExecutor(ip)
    # This command gets listening ports, PIDs, and the full command line.
    # We use sed to extract the pid safely from the ss output.
    cmd = """
    ss -tulpnH | awk '{print $5, $7}' | while read addr users; do
        pid=$(echo $users | sed -n 's/.*pid=\\([0-9]*\\),.*/\\1/p' | head -n 1)
        if [ -z "$pid" ]; then
            # Try without the trailing comma in case it's at the end
            pid=$(echo $users | sed -n 's/.*pid=\\([0-9]*\\).*/\\1/p' | head -n 1)
        fi
        if [ ! -z "$pid" ]; then
            command_line=$(ps -p $pid -o args=)
            echo "$pid|$addr|$command_line"
        fi
    done | sort -u
    """
    try:
        # Using a timeout or ensuring it doesn't hang
        status, stdout, stderr = await asyncio.to_thread(executor.execute, cmd)
        if status != 0:
            return []

        services = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                pid = parts[0]
                addr = parts[1]
                full_cmd = parts[2]

                # Split addr into IP and Port
                # Handle IPv6 [::]:80
                if ":" in addr:
                    ip_part, port = addr.rsplit(":", 1)
                else:
                    ip_part, port = addr, "???"

                services.append(
                    {"pid": pid, "ip": ip_part, "port": port, "command": full_cmd}
                )
        return services
    except Exception as e:
        return []
    finally:
        executor.close()


async def run_service_monitor():
    agora = Agora()
    await agora.initialize()

    with Live(auto_refresh=False) as live:
        while True:
            # Get registered services for cross-referencing descriptions
            registered = await agora.get_services()
            # Map (ip, port) -> service_info
            reg_map = {
                (s.vm_ip, str(s.service_name).split(":")[-1]): s for s in registered
            }

            table = Table(
                title="[bold green]Agent Chaos - Managed Services (/root/chaos/)[/bold green]",
                show_header=True,
                header_style="bold cyan",
                expand=True,
            )
            table.add_column("VM Host", style="magenta")
            table.add_column("PID", style="yellow")
            table.add_column("Port", style="bold green")
            table.add_column("Agent / Owner", style="cyan")
            table.add_column("Command / Binary", overflow="fold")
            table.add_column("Description", style="dim")

            # Fetch from all VMs in parallel
            tasks = [get_vm_services(ip) for ip in config.VM_IPS]
            results = await asyncio.gather(*tasks)

            found_any = False
            for ip, vm_services in zip(config.VM_IPS, results):
                for svc in vm_services:
                    # ONLY show processes running from /root/chaos/
                    if "/root/chaos/" in svc["command"]:
                        found_any = True

                        # Try to find agent registration
                        reg_info = reg_map.get((ip, svc["port"]))
                        owner = reg_info.agent_id if reg_info else "[dim]Unknown[/dim]"
                        desc = (
                            reg_info.description
                            if reg_info
                            else "[dim]Unregistered[/dim]"
                        )

                        table.add_row(
                            ip, svc["pid"], svc["port"], owner, svc["command"], desc
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

import asyncio
import json
import time
from ..agents.brain import Brain
from ..agents.personality import Personality
from ..communication.agora import Agora, ServiceInfo
from ..bridge.ssh import SSHExecutor
from ..bridge.discord import DiscordBridge
from ..utils.config import config
from ..utils.logger import agent_logger


class Agent:
    def __init__(self, user_id: int, agora: Agora, discord_bridge: DiscordBridge):
        self.user_id = str(user_id)
        self.username = str(user_id)
        self.avatar_url = None
        self.agora = agora
        self.discord_bridge = discord_bridge
        self.brain = Brain()
        self.personality = Personality(user_id)
        self.executors = {ip: SSHExecutor(ip) for ip in config.VM_IPS}
        self.history = []
        # Generate a consistent color based on user_id
        self.color = int(abs(hash(self.user_id)) % 0xFFFFFF)
        self.last_discord_update = 0
        self.last_query_id = 0

    async def run(self):
        self.username, self.avatar_url = await self.discord_bridge.get_user_info(
            int(self.user_id)
        )
        self.agent_label = f"chaos-{self.username}"

        await self.personality.initialize(self.brain)
        await self.agora.post(
            self.agent_label,
            f"Agent {self.agent_label} initialized and online.",
            "message",
        )

        while True:
            try:
                # 1. Observe the world (Agora)
                recent_activity = await self.agora.get_recent(limit=50)
                active_services = await self.agora.get_services()

                context = "Recent Agora Activity:\n"
                user_queries = []
                max_query_id = self.last_query_id

                for msg in recent_activity:
                    if msg.type == "user_query" and msg.id is not None:
                        if msg.id > self.last_query_id:
                            # Only pay attention to queries directed at me or general
                            if (
                                msg.agent_id == "all"
                                or msg.agent_id == self.agent_label
                            ):
                                user_queries.append(msg.content)
                                if msg.id > max_query_id:
                                    max_query_id = msg.id
                    context += f"[{msg.timestamp}] {msg.agent_id} ({msg.type}): {msg.content}\n"

                is_responding_to_query = len(user_queries) > 0
                if is_responding_to_query:
                    self.last_query_id = max_query_id
                    context += "\nURGENT: The human operator (Gradius) has asked you specifically:\n"
                    for q in user_queries:
                        context += f"- {q}\n"
                    context += "Please address these queries directly in your thoughts and responses.\n"

                if active_services:
                    context += "\nCurrently Registered Services:\n"
                    for svc in active_services:
                        context += f"- {svc.service_name} on {svc.vm_ip} (started by {svc.agent_id}): {svc.description}\n"

                # 2. Think
                system_prompt = self.personality.get_system_prompt(context)
                response_str = await self.brain.think(system_prompt, self.history[-10:])

                try:
                    # Parse JSON response
                    # Sometimes LLMs wrap JSON in code blocks
                    clean_response = response_str.strip()
                    if clean_response.startswith("```json"):
                        clean_response = clean_response[7:-3].strip()
                    elif clean_response.startswith("```"):
                        clean_response = clean_response[3:-3].strip()

                    response = json.loads(clean_response)
                except json.JSONDecodeError:
                    print(
                        f"Agent {self.user_id} failed to produce valid JSON: {response_str}"
                    )
                    await asyncio.sleep(10)
                    continue

                # 3. Act & Communicate
                agent_logger.log(
                    self.agent_label,
                    response.get("thought", ""),
                    action=json.dumps(response.get("actions", [])),
                    result="Pending...",
                    message=response.get("message"),
                    feeling=response.get("feeling"),
                )

                if "thought" in response:
                    await self.agora.post(
                        self.agent_label, response["thought"], "thought"
                    )

                if "feeling" in response:
                    await self.agora.post(
                        self.agent_label, response["feeling"], "feeling"
                    )

                if "message" in response and response["message"]:
                    await self.agora.post(
                        self.agent_label, response["message"], "message"
                    )
                    if is_responding_to_query:
                        await self.agora.post(
                            self.agent_label,
                            response["message"],
                            "operator_response",
                        )
                        # Log the interaction specifically
                        for q in user_queries:
                            agent_logger.log_interaction(
                                self.agent_label, q, response["message"]
                            )

                if "discord_update" in response and response["discord_update"]:
                    current_time = time.time()
                    # Bypass rate limit if responding to a direct interrogation
                    if is_responding_to_query or (
                        current_time - self.last_discord_update >= 30
                    ):
                        await self.discord_bridge.send_update(
                            response["discord_update"],
                            sender_name=f"chaos-{self.username}",
                            color=self.color,
                            avatar_url=self.avatar_url,
                        )
                        self.last_discord_update = current_time
                        # Sync to Agora so other agents are aware of the public update
                        await self.agora.post(
                            self.agent_label,
                            response["discord_update"],
                            "discord_update",
                        )
                        if is_responding_to_query:
                            await self.agora.post(
                                self.agent_label,
                                response["discord_update"],
                                "operator_response",
                            )
                            # Log interaction
                            for q in user_queries:
                                agent_logger.log_interaction(
                                    self.agent_label, q, response["discord_update"]
                                )
                    else:
                        # Log internally that we skipped a frequent update
                        print(
                            f"Agent {self.agent_label} Discord update rate-limited (last update was {current_time - self.last_discord_update:.1f}s ago)"
                        )

                if "services" in response:
                    for svc in response["services"]:
                        service_name = svc.get("service_name")
                        vm_ip = svc.get("vm_ip")
                        description = svc.get("description")
                        if service_name and vm_ip and description:
                            service_info = ServiceInfo(
                                service_name=service_name,
                                vm_ip=vm_ip,
                                agent_id=self.agent_label,
                                description=description,
                            )
                            await self.agora.register_service(service_info)
                            await self.agora.post(
                                self.agent_label,
                                f"Registered service: {service_name} on {vm_ip}",
                                "message",
                            )

                if "actions" in response:
                    for action in response["actions"]:
                        vm_ip = action.get("vm_ip")
                        command = action.get("command")
                        if vm_ip in self.executors and command:
                            executor = self.executors[vm_ip]
                            # Use asyncio.to_thread to avoid blocking the event loop with synchronous SSH calls
                            status, stdout, stderr = await asyncio.to_thread(
                                executor.execute, command
                            )
                            result = f"Command: {command}\nStatus: {status}\nSTDOUT: {stdout}\nSTDERR: {stderr}"
                            # Log the action result
                            agent_logger.log(
                                self.agent_label,
                                f"Result of: {command}",
                                action=command,
                                result=result,
                            )

                            await self.agora.post(
                                self.agent_label,
                                result,
                                "action",
                                metadata={"vm_ip": vm_ip, "command": command},
                            )

                # Add to local history
                self.history.append({"role": "assistant", "content": response_str})
                if len(self.history) > 20:
                    self.history = self.history[-20:]

            except Exception as e:
                print(f"Error in agent {self.user_id} loop: {e}")
                await asyncio.sleep(30)

            # Wait before next iteration
            await asyncio.sleep(15)

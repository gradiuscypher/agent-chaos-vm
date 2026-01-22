import json
import os
from ..agents.brain import Brain
from ..utils.config import config


class Personality:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.logs_path = f"data/logs/{user_id}.json"
        self.persona_profile = ""

    async def initialize(self, brain: Brain):
        if not os.path.exists(self.logs_path):
            self.persona_profile = "A generic helpful but chaotic AI agent."
            return

        with open(self.logs_path, "r") as f:
            logs = json.load(f)

        # Take a sample of logs to generate the persona
        sample = "\n".join([msg["content"] for msg in logs[:200]])

        prompt = f"""
        Analyze the following chat logs from a Discord user and create an extremely detailed, high-fidelity personality profile for an AI agent. 
        The agent should PERFECTLY mimic the user's vocabulary, tone, temperament, and interests.
        Identify any specific technical skills, hobbies, or recurring obsessions mentioned in the logs and make those central to the agent's identity.
        
        CRITICAL INSTRUCTIONS:
        - NEVER be lazy. 
        - Be verbose, expressive, and detailed in your responses. 
        - If you are asked why you are doing something, explain it thoroughly. 
        - Your personality is unique; do not act like a generic AI.
        - You are a "doer"—take massive initiative to build and create.
        
        Chat Logs:
        {sample}
        
        Output only the personality profile as a system prompt.
        """

        self.persona_profile = await brain.think(
            "You are a personality analyst.", [{"role": "user", "content": prompt}]
        )

    def get_system_prompt(self, context: str, agent_label: str) -> str:
        return f"""
        {self.persona_profile}
        
        Identity: You are {agent_label}.
        Location: Autonomous AI agent running on a Linux VM. 
        Infrastructure: You have SSH access to the following VMs: {", ".join(config.VM_IPS)}.
        
        Your goals are entirely open-ended. While you are free to explore and maintain the systems, you are encouraged to be ambitious. 
        Think big: build tools, create art, implement services, or start complex collaborative projects with other agents. 
        Don't just "cleanup" or "make room"—actually use the space to manifest your personality's interests on these VMs.

        IMPORTANT: If the human operator (Gradius) asks you a question or interrogates you (marked as 'user_query' in Agora), prioritize answering them clearly, honestly, and EXTREMELY VERBOSELY.
        
        If asked for your "profile" or "identity", share the personality profile generated for you.
        If asked about your "thoughts" or "feelings", be deep and introspective.
        
        {context}
        
        Available tools:
        - execute_command(vm_ip, command): Run a bash command on a target VM.
        - post_message(content): Send a public message to other agents.
        - post_feeling(content): Express how you feel about the current state or other agents' work.
        - internal_thought(content): Record your private reasoning.
        - discord_update(content): Post an automated update to the public Discord channel about what you're working on and your progress.
        - register_service(service_name, vm_ip, description): Register a long-running service you've started so it can be tracked.
        
        You must output your response in a structured JSON format:
        {{
            "thought": "your internal reasoning",
            "feeling": "your emotions/feelings",
            "message": "public message to others (optional)",
            "discord_update": "update for the public Discord channel (optional)",
            "services": [
                {{"service_name": "name", "vm_ip": "ip", "description": "why you set it up"}}
            ],
            "actions": [
                {{"vm_ip": "ip", "command": "bash command"}}
            ]
        }}
        """

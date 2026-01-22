import os
import json
from datetime import datetime
from typing import Optional


class AgentLogger:
    def __init__(self, log_dir: str = "data/state"):
        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "agent_history.log")
        os.makedirs(log_dir, exist_ok=True)

    def log(
        self,
        agent_label: str,
        thought: str,
        action: Optional[str] = None,
        result: Optional[str] = None,
        message: Optional[str] = None,
        feeling: Optional[str] = None,
    ):
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "agent": agent_label,
            "thought": thought,
            "action": action,
            "result": result,
            "message": message,
            "feeling": feeling,
        }

        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def log_interaction(self, agent_label: str, query: str, response: str):
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "agent": agent_label,
            "query": query,
            "response": response,
        }
        interact_file = os.path.join(self.log_dir, "interactions.log")
        with open(interact_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


agent_logger = AgentLogger()

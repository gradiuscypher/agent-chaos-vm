import paramiko
import os
from typing import Tuple


class SSHExecutor:
    def __init__(self, host: str, user: str = "root"):
        self.host = host
        self.user = user
        self.client = None

    def connect(self):
        if self.client:
            return
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        # Assuming the default SSH key is authorized on the target VMs
        self.client.connect(self.host, username=self.user)

    def execute(self, command: str) -> Tuple[int, str, str]:
        self.connect()
        assert self.client is not None
        stdin, stdout, stderr = self.client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        return exit_status, stdout.read().decode(), stderr.read().decode()

    def close(self):
        if self.client:
            self.client.close()
            self.client = None

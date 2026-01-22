import aiosqlite
import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from contextlib import asynccontextmanager


class AgoraMessage(BaseModel):
    id: Optional[int] = None
    agent_id: str
    content: str
    type: str  # 'message', 'thought', 'action', 'feeling'
    timestamp: Optional[str] = None
    metadata: Optional[str] = None


class ServiceInfo(BaseModel):
    id: Optional[int] = None
    service_name: str
    vm_ip: str
    agent_id: str
    start_time: Optional[str] = None
    description: str
    status: str = "running"


class AgentRegistry(BaseModel):
    agent_id: str
    pid: int
    status: str
    total_tokens: int = 0
    last_context_tokens: int = 0
    last_heartbeat: Optional[str] = None


class Agora:
    def __init__(self, db_path: str = "data/state/agora.sqlite"):
        self.db_path = db_path

    @asynccontextmanager
    async def _get_db(self):
        # Increase timeout and enable WAL mode for better concurrency
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            yield db

    async def initialize(self):
        async with self._get_db() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agora (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    content TEXT,
                    type TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT,
                    vm_ip TEXT,
                    agent_id TEXT,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    status TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS registry (
                    agent_id TEXT PRIMARY KEY,
                    pid INTEGER,
                    status TEXT,
                    total_tokens INTEGER DEFAULT 0,
                    last_context_tokens INTEGER DEFAULT 0,
                    last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def update_registry(
        self,
        agent_id: str,
        pid: int,
        status: str,
        total_tokens: int,
        last_context_tokens: int,
    ):
        async with self._get_db() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO registry (agent_id, pid, status, total_tokens, last_context_tokens, last_heartbeat)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (agent_id, pid, status, total_tokens, last_context_tokens),
            )
            await db.commit()

    async def get_registry(self) -> List[AgentRegistry]:
        registry = []
        async with self._get_db() as db:
            async with db.execute(
                "SELECT agent_id, pid, status, total_tokens, last_context_tokens, last_heartbeat FROM registry"
            ) as cursor:
                async for row in cursor:
                    registry.append(
                        AgentRegistry(
                            agent_id=row[0],
                            pid=row[1],
                            status=row[2],
                            total_tokens=row[3],
                            last_context_tokens=row[4],
                            last_heartbeat=row[5],
                        )
                    )
        return registry

    async def register_service(self, service: ServiceInfo):
        async with self._get_db() as db:
            await db.execute(
                "INSERT INTO services (service_name, vm_ip, agent_id, description, status) VALUES (?, ?, ?, ?, ?)",
                (
                    service.service_name,
                    service.vm_ip,
                    service.agent_id,
                    service.description,
                    service.status,
                ),
            )
            await db.commit()

    async def get_services(self) -> List[ServiceInfo]:
        services = []
        async with self._get_db() as db:
            async with db.execute(
                "SELECT id, service_name, vm_ip, agent_id, start_time, description, status FROM services"
            ) as cursor:
                async for row in cursor:
                    services.append(
                        ServiceInfo(
                            id=row[0],
                            service_name=row[1],
                            vm_ip=row[2],
                            agent_id=row[3],
                            start_time=row[4],
                            description=row[5],
                            status=row[6],
                        )
                    )
        return services

    async def post(
        self,
        agent_id: str,
        content: str,
        msg_type: str,
        metadata: Optional[dict] = None,
    ):
        # type 'user_query' is special for interactions
        async with self._get_db() as db:
            await db.execute(
                "INSERT INTO agora (agent_id, content, type, metadata) VALUES (?, ?, ?, ?)",
                (
                    agent_id,
                    content,
                    msg_type,
                    json.dumps(metadata) if metadata else None,
                ),
            )
            await db.commit()

    async def get_recent(
        self,
        limit: int = 50,
        msg_type: Optional[str] = None,
        after_id: Optional[int] = None,
    ) -> List[AgoraMessage]:
        query = "SELECT id, agent_id, content, type, timestamp, metadata FROM agora WHERE 1=1"
        params = []
        if msg_type:
            query += " AND type = ?"
            params.append(msg_type)
        if after_id:
            query += " AND id > ?"
            params.append(after_id)

        # If we are looking for messages AFTER a specific ID, we want the OLDEST ones first
        # to ensure we don't skip anything in a stream.
        # If we are just getting "recent" without after_id, we want the NEWEST.
        if after_id:
            query += " ORDER BY id ASC LIMIT ?"
        else:
            query += " ORDER BY id DESC LIMIT ?"

        params.append(limit)

        messages = []
        async with self._get_db() as db:
            async with db.execute(query, params) as cursor:
                async for row in cursor:
                    messages.append(
                        AgoraMessage(
                            id=row[0],
                            agent_id=row[1],
                            content=row[2],
                            type=row[3],
                            timestamp=row[4],
                            metadata=row[5],
                        )
                    )

        # If we used DESC (no after_id), we should reverse to return chronological order
        return messages if after_id else messages[::-1]

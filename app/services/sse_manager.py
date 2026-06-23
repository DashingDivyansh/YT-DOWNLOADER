import asyncio
import json
from typing import Dict, Any

class SSEManager:
    def __init__(self):
        # Maps session_id to an asyncio Queue
        self.sessions: Dict[str, asyncio.Queue] = {}

    def create_session(self, session_id: str):
        self.sessions[session_id] = asyncio.Queue()

    async def publish(self, session_id: str, message: Dict[str, Any]):
        if session_id in self.sessions:
            await self.sessions[session_id].put(message)

    def complete_session(self, session_id: str):
        queue = self.sessions.get(session_id)
        if not queue:
            return
        try:
            asyncio.create_task(queue.put({"status": "close"}))
        except RuntimeError:
            queue.put_nowait({"status": "close"})

    async def stream_generator(self, session_id: str):
        if session_id not in self.sessions:
            return
        
        queue = self.sessions[session_id]
        try:
            while True:
                message = await queue.get()
                if message.get("status") == "close":
                    yield {
                        "event": "close",
                        "data": "{}"
                    }
                    break
                yield {
                    "event": "message",
                    "data": json.dumps(message)
                }
        finally:
            self.sessions.pop(session_id, None)

sse_manager = SSEManager()

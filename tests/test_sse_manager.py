import pytest
import asyncio
from app.services.sse_manager import SSEManager


@pytest.fixture
def manager():
    return SSEManager()


class TestSSEManager:
    def test_create_session(self, manager):
        manager.create_session("test-session")
        assert "test-session" in manager.sessions

    def test_create_multiple_sessions(self, manager):
        manager.create_session("s1")
        manager.create_session("s2")
        assert "s1" in manager.sessions
        assert "s2" in manager.sessions

    @pytest.mark.asyncio
    async def test_publish_and_receive(self, manager):
        manager.create_session("s1")
        await manager.publish("s1", {"video_id": "v1", "status": "downloading", "percent": 50})
        
        msg = await manager.sessions["s1"].get()
        assert msg["video_id"] == "v1"
        assert msg["percent"] == 50

    @pytest.mark.asyncio
    async def test_publish_to_nonexistent_session(self, manager):
        """Publishing to a session that doesn't exist should not raise."""
        await manager.publish("nonexistent", {"data": "test"})

    @pytest.mark.asyncio
    async def test_stream_generator_yields_messages(self, manager):
        manager.create_session("s1")
        await manager.publish("s1", {"video_id": "v1", "status": "downloading", "percent": 25})
        await manager.publish("s1", {"status": "close"})

        events = []
        async for event in manager.stream_generator("s1"):
            events.append(event)

        assert len(events) == 2
        assert events[0]["event"] == "message"
        assert events[1]["event"] == "close"

    @pytest.mark.asyncio
    async def test_stream_generator_cleans_up_session(self, manager):
        manager.create_session("s1")
        await manager.publish("s1", {"status": "close"})

        async for _ in manager.stream_generator("s1"):
            pass

        assert "s1" not in manager.sessions

    @pytest.mark.asyncio
    async def test_stream_nonexistent_session_returns_immediately(self, manager):
        events = []
        async for event in manager.stream_generator("nonexistent"):
            events.append(event)
        assert len(events) == 0

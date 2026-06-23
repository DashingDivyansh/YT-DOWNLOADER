import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.models.schemas import FetchResponse, VideoInfo

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "YT Downloader Pro" in response.text


def test_missing_download_file_returns_404():
    response = client.get("/api/file/not-present.mp4")
    assert response.status_code == 404


def test_download_file_from_playlist_folder(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "DOWNLOAD_DIR", str(tmp_path))
    folder = tmp_path / "My Playlist"
    folder.mkdir()
    output = folder / "001 - First.mp4"
    output.write_text("data")

    response = client.get("/api/file/My%20Playlist/001%20-%20First.mp4")
    assert response.status_code == 200

@patch("app.api.routes.fetch_metadata", new_callable=AsyncMock)
def test_fetch_video(mock_fetch):
    # Mocking the fetch_metadata response
    mock_fetch.return_value = FetchResponse(
        type="video",
        videos=[
            VideoInfo(
                id="dQw4w9WgXcQ",
                title="Never Gonna Give You Up",
                thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                duration="3:33",
                channel="Rick Astley"
            )
        ],
        qualities=["1080p", "720p"]
    )
    
    response = client.post(
        "/api/fetch",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "video"
    assert len(data["videos"]) == 1
    assert data["videos"][0]["title"] == "Never Gonna Give You Up"
    assert "1080p" in data["qualities"]

@patch("app.api.routes.start_download_task", new_callable=AsyncMock)
def test_start_download(mock_download_task):
    response = client.post(
        "/api/download",
        json={
            "videos": ["dQw4w9WgXcQ", "abcdefghijk"],
            "quality": "720p",
            "concurrent": 3
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    # Ensure background task would have been triggered
    assert mock_download_task.called


@patch("app.api.routes.start_download_task", new_callable=AsyncMock)
def test_start_playlist_repair_download(mock_download_task):
    response = client.post(
        "/api/download",
        json={
            "videos": ["dQw4w9WgXcQ"],
            "quality": "720p",
            "concurrent": 2,
            "playlist_title": "My Playlist",
            "repair": True,
            "items": [
                {"id": "dQw4w9WgXcQ", "title": "First", "index": 1}
            ],
        }
    )

    assert response.status_code == 200
    assert mock_download_task.called
    args = mock_download_task.call_args.args
    assert args[4] == "My Playlist"
    assert args[6] is True

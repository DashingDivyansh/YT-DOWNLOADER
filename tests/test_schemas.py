import pytest
from app.models.schemas import (
    FetchRequest, FetchResponse, VideoInfo,
    DownloadItem, DownloadRequest, DownloadResponse
)
from pydantic import ValidationError


class TestFetchRequest:
    def test_valid_url(self):
        req = FetchRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert req.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_empty_url_is_allowed_by_schema(self):
        """Schema only validates type, not content. Route-level validation handles empty URLs."""
        req = FetchRequest(url="")
        assert req.url == ""

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            FetchRequest()


class TestVideoInfo:
    def test_valid_video_info(self):
        v = VideoInfo(
            id="abc123",
            title="Test Video",
            thumbnail="https://example.com/thumb.jpg",
            duration="5:30",
            channel="Test Channel"
        )
        assert v.id == "abc123"
        assert v.title == "Test Video"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            VideoInfo(id="abc", title="Test")


class TestFetchResponse:
    def test_single_video_response(self):
        resp = FetchResponse(
            type="video",
            videos=[
                VideoInfo(id="v1", title="T", thumbnail="t.jpg", duration="1:00", channel="C")
            ],
            qualities=["720p", "480p"]
        )
        assert resp.type == "video"
        assert resp.playlist_title is None
        assert len(resp.videos) == 1

    def test_playlist_response(self):
        resp = FetchResponse(
            type="playlist",
            playlist_title="My Playlist",
            videos=[
                VideoInfo(id="v1", title="T1", thumbnail="t1.jpg", duration="1:00", channel="C"),
                VideoInfo(id="v2", title="T2", thumbnail="t2.jpg", duration="2:00", channel="C"),
            ],
            qualities=["1080p", "720p"]
        )
        assert resp.type == "playlist"
        assert resp.playlist_title == "My Playlist"
        assert len(resp.videos) == 2

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            FetchResponse(
                type="invalid",
                videos=[],
                qualities=[]
            )


class TestDownloadRequest:
    def test_valid_request(self):
        req = DownloadRequest(
            videos=["v1", "v2"],
            quality="720p",
            concurrent=3
        )
        assert req.concurrent == 3

    def test_default_concurrent(self):
        req = DownloadRequest(videos=["v1"], quality="720p")
        assert req.concurrent == 3

    def test_concurrent_below_min_raises(self):
        with pytest.raises(ValidationError):
            DownloadRequest(videos=["v1"], quality="720p", concurrent=0)

    def test_concurrent_above_max_raises(self):
        with pytest.raises(ValidationError):
            DownloadRequest(videos=["v1"], quality="720p", concurrent=10)

    def test_concurrent_boundaries(self):
        req_min = DownloadRequest(videos=["v1"], quality="720p", concurrent=1)
        req_max = DownloadRequest(videos=["v1"], quality="720p", concurrent=5)
        assert req_min.concurrent == 1
        assert req_max.concurrent == 5

    def test_playlist_download_metadata(self):
        req = DownloadRequest(
            videos=["v1"],
            quality="720p",
            playlist_title="My Playlist",
            repair=True,
            items=[DownloadItem(id="v1", title="First", index=1)],
        )
        assert req.playlist_title == "My Playlist"
        assert req.repair is True
        assert req.items[0].index == 1

    def test_download_item_index_must_be_positive(self):
        with pytest.raises(ValidationError):
            DownloadItem(id="v1", title="First", index=0)


class TestDownloadResponse:
    def test_valid_response(self):
        resp = DownloadResponse(session_id="abc-123")
        assert resp.session_id == "abc-123"

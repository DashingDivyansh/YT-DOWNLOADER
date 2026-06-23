import os
import pytest
from app.models.schemas import DownloadItem
from app.services.youtube import (
    DOWNLOAD_DIR,
    QUALITIES,
    _format_duration,
    _find_existing_playlist_file,
    _reconcile_existing_playlist_file,
    _reconcile_playlist_files,
    _relative_download_path,
    _resolve_final_filename,
    get_format_string,
    normalize_video_url,
    sanitize_path_component,
    strip_ansi,
)


class TestStripAnsi:
    """Tests for ANSI escape code removal."""

    def test_strip_color_codes(self):
        assert strip_ansi("\x1b[0;94m5.2MiB/s\x1b[0m") == "5.2MiB/s"

    def test_strip_multiple_codes(self):
        assert strip_ansi("\x1b[0;94m\x1b[0m45.0%\x1b[0m") == "45.0%"

    def test_empty_string_returns_na(self):
        assert strip_ansi("") == "N/A"

    def test_none_returns_na(self):
        assert strip_ansi(None) == "N/A"

    def test_plain_string_unchanged(self):
        assert strip_ansi("hello") == "hello"


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_seconds_only(self):
        assert _format_duration(45) == "0:45"

    def test_minutes_and_seconds(self):
        assert _format_duration(213) == "3:33"

    def test_hours(self):
        assert _format_duration(3661) == "1:01:01"

    def test_string_input(self):
        assert _format_duration("120") == "2:00"

    def test_none_returns_na(self):
        assert _format_duration(None) == "N/A"

    def test_invalid_string(self):
        assert _format_duration("not_a_number") == "not_a_number"

    def test_zero(self):
        assert _format_duration(0) == "0:00"


class TestGetFormatString:
    """Tests for the quality-to-yt-dlp format string mapping."""

    def test_1080p(self):
        result = get_format_string("1080p")
        assert "1080" in result
        assert "bv*" in result
        assert "ba" in result

    def test_720p(self):
        result = get_format_string("720p")
        assert "720" in result

    def test_480p(self):
        result = get_format_string("480p")
        assert "480" in result

    def test_360p(self):
        result = get_format_string("360p")
        assert "360" in result

    def test_audio_only(self):
        result = get_format_string("Audio Only (MP3)")
        assert result == "bestaudio/best"

    def test_best_available(self):
        result = get_format_string("Best Available")
        assert result == "bv*+ba/b"

    def test_unknown_quality_falls_through_to_best(self):
        """Any unrecognized quality string should default to best available."""
        result = get_format_string("some_random_quality")
        assert result == "bv*+ba/b"


class TestNormalizeVideoUrl:
    def test_video_id(self):
        assert normalize_video_url("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123"
        assert normalize_video_url(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_short_url(self):
        assert normalize_video_url("https://youtu.be/dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_invalid_ref_raises(self):
        with pytest.raises(ValueError):
            normalize_video_url("not-a-youtube-video")


class TestResolveFinalFilename:
    def test_resolves_info_filepath(self, tmp_path):
        output = tmp_path / "video.mp4"
        output.write_text("data")
        assert _resolve_final_filename({"filepath": str(output)}) == "video.mp4"

    def test_resolves_requested_download_filepath(self, tmp_path):
        output = tmp_path / "audio.mp3"
        output.write_text("data")
        info = {"requested_downloads": [{"filepath": str(output)}]}
        assert _resolve_final_filename(info) == "audio.mp3"

    def test_falls_back_to_basename(self):
        assert _resolve_final_filename({}, r"C:\missing\fallback.mp4") == "fallback.mp4"


class TestPlaylistFileHelpers:
    def test_sanitize_path_component_removes_windows_invalid_chars(self):
        assert sanitize_path_component('My: Playlist? <2026>') == "My_ Playlist_ _2026_"

    def test_relative_download_path_uses_playlist_folder(self):
        assert _relative_download_path("001 - Video.mp4", "My Playlist") == "My Playlist/001 - Video.mp4"

    def test_find_existing_playlist_file_by_index(self, tmp_path, monkeypatch):
        import app.services.youtube as youtube

        monkeypatch.setattr(youtube, "DOWNLOAD_DIR", str(tmp_path))
        folder = tmp_path / "My Playlist"
        folder.mkdir()
        (folder / "001 - First.mp4").write_text("data")

        assert _find_existing_playlist_file("My Playlist", 1) == "001 - First.mp4"
        assert _find_existing_playlist_file("My Playlist", 2) is None

    def test_reconcile_moves_root_file_into_playlist_folder(self, tmp_path, monkeypatch):
        import app.services.youtube as youtube

        monkeypatch.setattr(youtube, "DOWNLOAD_DIR", str(tmp_path))
        root_file = tmp_path / "First_Video.mp4"
        root_file.write_text("data")

        result = _reconcile_existing_playlist_file("My Playlist", 1, "First Video")

        assert result == "001 - First_Video.mp4"
        assert not root_file.exists()
        assert (tmp_path / "My Playlist" / "001 - First_Video.mp4").exists()

    def test_reconcile_renames_wrong_playlist_filename(self, tmp_path, monkeypatch):
        import app.services.youtube as youtube

        monkeypatch.setattr(youtube, "DOWNLOAD_DIR", str(tmp_path))
        folder = tmp_path / "My Playlist"
        folder.mkdir()
        wrong_file = folder / "First_Video.mp4"
        wrong_file.write_text("data")

        result = _reconcile_existing_playlist_file("My Playlist", 7, "First Video")

        assert result == "007 - First_Video.mp4"
        assert not wrong_file.exists()
        assert (folder / "007 - First_Video.mp4").exists()

    def test_reconcile_ignores_empty_files(self, tmp_path, monkeypatch):
        import app.services.youtube as youtube

        monkeypatch.setattr(youtube, "DOWNLOAD_DIR", str(tmp_path))
        (tmp_path / "First_Video.mp4").write_text("")

        assert _reconcile_existing_playlist_file("My Playlist", 1, "First Video") is None

    def test_bulk_reconcile_playlist_files(self, tmp_path, monkeypatch):
        import app.services.youtube as youtube

        monkeypatch.setattr(youtube, "DOWNLOAD_DIR", str(tmp_path))
        (tmp_path / "First_Video.mp4").write_text("data")
        (tmp_path / "Second_Video.mp4").write_text("data")

        result = _reconcile_playlist_files("My Playlist", [
            DownloadItem(id="v1", title="First Video", index=1),
            DownloadItem(id="v2", title="Second Video", index=2),
        ])

        assert result == {
            "v1": "001 - First_Video.mp4",
            "v2": "002 - Second_Video.mp4",
        }
        assert (tmp_path / "My Playlist" / "001 - First_Video.mp4").exists()
        assert (tmp_path / "My Playlist" / "002 - Second_Video.mp4").exists()


class TestQualities:
    def test_qualities_list_not_empty(self):
        assert len(QUALITIES) > 0

    def test_qualities_contains_expected(self):
        assert "Best Available" in QUALITIES
        assert "1080p" in QUALITIES
        assert "720p" in QUALITIES
        assert "Audio Only (MP3)" in QUALITIES


class TestDownloadDir:
    def test_download_dir_exists(self):
        assert os.path.isdir(DOWNLOAD_DIR)

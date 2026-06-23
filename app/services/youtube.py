import yt_dlp
import re
import os
import concurrent.futures
import asyncio
import logging
import imageio_ffmpeg
import json
from urllib.parse import parse_qs, urlparse
from app.services.sse_manager import sse_manager
from app.models.schemas import DownloadItem, VideoInfo, FetchResponse

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../downloads"))

QUALITIES = ["Best Available", "1080p", "720p", "480p", "360p", "Audio Only (MP3)"]
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Regex to strip ANSI escape sequences from yt-dlp strings
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def strip_ansi(text: str) -> str:
    """Remove ANSI color codes from a string."""
    if not text:
        return "N/A"
    return _ANSI_RE.sub('', text).strip()


def get_format_string(quality: str) -> str:
    """Map a human-readable quality label to a yt-dlp format selector."""
    quality_map = {
        "Best Available": "bv*+ba/b",
        "1080p": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "720p":  "bv*[height<=720]+ba/b[height<=720]/b",
        "480p":  "bv*[height<=480]+ba/b[height<=480]/b",
        "360p":  "bv*[height<=360]+ba/b[height<=360]/b",
        "Audio Only (MP3)": "bestaudio/best",
    }
    return quality_map.get(quality, "bv*+ba/b")


def _format_duration(seconds) -> str:
    """Convert seconds (int or str) to a human readable MM:SS or HH:MM:SS string."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return str(seconds) if seconds else "N/A"
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def normalize_video_url(video_ref: str) -> str:
    """Accept a YouTube video id or URL and return a canonical watch URL."""
    video_ref = (video_ref or "").strip()
    if not video_ref:
        raise ValueError("Missing video id or URL.")
    if YOUTUBE_VIDEO_ID_RE.match(video_ref):
        return f"https://www.youtube.com/watch?v={video_ref}"

    parsed = urlparse(video_ref)
    host = parsed.netloc.lower().removeprefix("www.")
    if host in {"youtube.com", "m.youtube.com"}:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if YOUTUBE_VIDEO_ID_RE.match(video_id):
            return f"https://www.youtube.com/watch?v={video_id}"
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if YOUTUBE_VIDEO_ID_RE.match(video_id):
            return f"https://www.youtube.com/watch?v={video_id}"

    raise ValueError(f"Invalid YouTube video id or URL: {video_ref}")


def _video_id_from_entry(entry: dict) -> str:
    """Extract a usable video id from a yt-dlp playlist entry."""
    for key in ("id", "display_id"):
        value = entry.get(key)
        if value and YOUTUBE_VIDEO_ID_RE.match(value):
            return value

    for key in ("url", "webpage_url"):
        value = entry.get(key)
        if not value:
            continue
        try:
            return parse_qs(urlparse(normalize_video_url(value)).query)["v"][0]
        except (KeyError, ValueError):
            continue
    return ""


def _existing_basename(path: str | None) -> str | None:
    if not path:
        return None
    if os.path.exists(path):
        return os.path.basename(path)
    return None


def _resolve_final_filename(info: dict, fallback_filename: str | None = None) -> str | None:
    """Find the actual file produced by yt-dlp after merge/conversion."""
    candidates = []
    if isinstance(info, dict):
        candidates.extend([
            info.get("filepath"),
            info.get("_filename"),
            info.get("filename"),
        ])
        for item in info.get("requested_downloads") or []:
            if isinstance(item, dict):
                candidates.extend([
                    item.get("filepath"),
                    item.get("_filename"),
                    item.get("filename"),
                ])

    candidates.append(fallback_filename)
    for candidate in candidates:
        basename = _existing_basename(candidate)
        if basename:
            return basename
    return os.path.basename(fallback_filename) if fallback_filename else None


def sanitize_path_component(value: str, fallback: str = "Untitled") -> str:
    """Make a folder/file component safe for Windows and readable."""
    value = strip_ansi(value or "").strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:120] or fallback


def _safe_video_stem(title: str | None, fallback: str) -> str:
    """Match yt-dlp's restricted filename style for previously downloaded files."""
    stem = yt_dlp.utils.sanitize_filename(title or fallback, restricted=True)
    return os.path.splitext(stem)[0] or fallback


def _playlist_folder(playlist_title: str | None) -> str | None:
    if not playlist_title:
        return None
    return os.path.join(DOWNLOAD_DIR, sanitize_path_component(playlist_title, "Playlist"))


def _relative_download_path(filename: str, playlist_title: str | None = None) -> str:
    if not playlist_title:
        return filename
    return f"{sanitize_path_component(playlist_title, 'Playlist')}/{filename}"


def _find_existing_playlist_file(playlist_title: str | None, index: int | None) -> str | None:
    folder = _playlist_folder(playlist_title)
    if not folder or not index:
        return None
    prefix = f"{index:03d} - "
    if not os.path.isdir(folder):
        return None
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if (
            os.path.isfile(path)
            and name.startswith(prefix)
            and not name.endswith(".part")
            and os.path.getsize(path) > 0
        ):
            return name
    return None


def _strip_playlist_number(stem: str) -> str:
    return re.sub(r"^\d{1,4}\s*-\s*", "", stem).strip()


def _is_complete_media_file(path: str) -> bool:
    media_exts = {".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".opus"}
    _, ext = os.path.splitext(path)
    return (
        os.path.isfile(path)
        and ext.lower() in media_exts
        and not path.endswith(".part")
        and os.path.getsize(path) > 0
    )


def _unique_destination_path(folder: str, filename: str) -> str:
    destination = os.path.join(folder, filename)
    if not os.path.exists(destination):
        return destination

    stem, ext = os.path.splitext(filename)
    counter = 2
    while True:
        candidate = os.path.join(folder, f"{stem} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def _rename_or_move_playlist_file(source_path: str, playlist_title: str, index: int, title: str) -> str:
    folder = _playlist_folder(playlist_title)
    if not folder:
        return os.path.basename(source_path)
    os.makedirs(folder, exist_ok=True)

    _, ext = os.path.splitext(source_path)
    target_name = f"{index:03d} - {_safe_video_stem(title, os.path.splitext(os.path.basename(source_path))[0])}{ext}"
    target_path = os.path.join(folder, target_name)
    source_abs = os.path.abspath(source_path)
    target_abs = os.path.abspath(target_path)

    if source_abs == target_abs:
        return target_name
    if os.path.exists(target_path) and _is_complete_media_file(target_path):
        return os.path.basename(target_path)

    target_path = _unique_destination_path(folder, target_name)
    os.replace(source_path, target_path)
    return os.path.basename(target_path)


def _reconcile_existing_playlist_file(playlist_title: str | None, index: int | None, title: str | None) -> str | None:
    """Move/rename an already-downloaded playlist item into its ordered folder."""
    if not playlist_title or not index:
        return None

    existing = _find_existing_playlist_file(playlist_title, index)
    if existing:
        return existing

    folder = _playlist_folder(playlist_title)
    if not folder:
        return None
    os.makedirs(folder, exist_ok=True)

    expected_stem = _safe_video_stem(title, str(index))
    for search_dir in (folder, DOWNLOAD_DIR):
        if not os.path.isdir(search_dir):
            continue
        for name in os.listdir(search_dir):
            path = os.path.join(search_dir, name)
            if not _is_complete_media_file(path):
                continue
            stem, _ = os.path.splitext(name)
            if _strip_playlist_number(stem) == expected_stem:
                return _rename_or_move_playlist_file(path, playlist_title, index, title or expected_stem)
    return None


def _write_playlist_manifest(playlist_title: str | None, items: list[DownloadItem]):
    folder = _playlist_folder(playlist_title)
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    manifest_path = os.path.join(folder, "playlist_manifest.json")
    payload = {
        "playlist_title": playlist_title,
        "videos": [item.model_dump() for item in sorted(items, key=lambda item: item.index)],
    }
    with open(manifest_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _reconcile_playlist_files(playlist_title: str | None, items: list[DownloadItem]) -> dict[str, str]:
    """Organize all existing playlist files before download workers run."""
    if not playlist_title:
        return {}
    reconciled = {}
    for item in items:
        filename = _reconcile_existing_playlist_file(playlist_title, item.index, item.title)
        if filename:
            reconciled[item.id] = filename
    return reconciled


def fetch_metadata_sync(url: str) -> FetchResponse:
    """Extract video or playlist metadata without downloading."""
    url = (url or "").strip()
    if not url:
        raise ValueError("Please provide a YouTube video or playlist URL.")

    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                raise ValueError("Could not extract metadata.")

            if info.get('_type') == 'playlist' or 'entries' in info:
                videos = []
                for position, entry in enumerate(info.get('entries', []), start=1):
                    if entry is None:
                        continue
                    vid = _video_id_from_entry(entry)
                    if not vid:
                        continue
                    index = entry.get('playlist_index') or position
                    videos.append(VideoInfo(
                        id=vid,
                        title=entry.get('title', 'Unknown Title'),
                        thumbnail=entry.get('thumbnail') or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        duration=_format_duration(entry.get('duration')),
                        channel=entry.get('uploader') or entry.get('channel', 'Unknown Channel'),
                        index=int(index),
                    ))
                if not videos:
                    raise ValueError("No downloadable videos were found in this playlist.")
                return FetchResponse(
                    type="playlist",
                    playlist_title=info.get('title', 'YouTube Playlist'),
                    videos=videos,
                    qualities=QUALITIES
                )
            else:  # Single video
                video = VideoInfo(
                    id=info.get('id', ''),
                    title=info.get('title', 'Unknown Title'),
                    thumbnail=info.get('thumbnail') or f"https://i.ytimg.com/vi/{info.get('id', '')}/hqdefault.jpg",
                    duration=_format_duration(info.get('duration')),
                    channel=info.get('uploader') or info.get('channel', 'Unknown Channel')
                )
                return FetchResponse(
                    type="video",
                    videos=[video],
                    qualities=QUALITIES
                )
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp extraction error for {url}: {e}")
        raise ValueError(f"Could not extract metadata: {strip_ansi(str(e))}")
    except Exception as e:
        logger.error(f"Unexpected extraction error for {url}: {e}")
        raise ValueError(f"Unexpected error: {str(e)}")


async def fetch_metadata(url: str) -> FetchResponse:
    """Run the blocking metadata extraction in a thread pool."""
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, fetch_metadata_sync, url)


def safe_publish(session_id: str, message: dict, loop: asyncio.AbstractEventLoop):
    """Safely publish to SSE without raising exceptions in worker threads/hooks."""
    try:
        asyncio.run_coroutine_threadsafe(sse_manager.publish(session_id, message), loop)
    except Exception as e:
        logger.error(f"Failed to publish SSE message: {e}")

def download_video_sync(
    video_id: str,
    quality: str,
    session_id: str,
    loop: asyncio.AbstractEventLoop,
    playlist_title: str | None = None,
    title: str | None = None,
    index: int | None = None,
    repair: bool = False,
):
    """
    Download a single video. Runs in a worker thread.
    Uses progress_hooks for download % and postprocessor_hooks for the real final filename.
    """
    final_filename = None  # Will be set by postprocessor_hook
    terminal_sent = False  # Track if done or error was already sent
    display_id = video_id

    existing_file = _reconcile_existing_playlist_file(playlist_title, index, title)
    if existing_file:
        safe_publish(session_id, {
            "video_id": display_id,
            "status": "done",
            "filename": _relative_download_path(existing_file, playlist_title),
            "skipped": True,
        }, loop)
        return

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = strip_ansi(d.get('_percent_str', '0.0%')).replace('%', '')
            speed = strip_ansi(d.get('_speed_str', 'N/A'))
            eta = strip_ansi(d.get('_eta_str', 'N/A'))
            try:
                percent = round(float(percent_str), 1)
            except ValueError:
                percent = 0.0

            message = {
                "video_id": video_id,
                "status": "downloading",
                "percent": percent,
                "speed": speed,
                "eta": eta
            }
            safe_publish(session_id, message, loop)

        elif d['status'] == 'finished':
            # This fires when the raw stream download is done, BEFORE post-processing.
            nonlocal final_filename
            filename = d.get('filename')
            if filename:
                final_filename = filename
            logger.info(f"[{display_id}] Raw download finished: {os.path.basename(final_filename or '')}")
            
        elif d['status'] == 'error':
            nonlocal terminal_sent
            message = {
                "video_id": video_id,
                "status": "error",
                "error": strip_ansi(d.get('error', 'Unknown Error'))
            }
            safe_publish(session_id, message, loop)
            terminal_sent = True

    def postprocessor_hook(d):
        """Fires after each post-processor (merge, convert, etc.) completes."""
        nonlocal final_filename
        if d['status'] == 'finished':
            # The 'info_dict' key holds the final filepath after all processing
            info = d.get('info_dict', {})
            filepath = info.get('filepath') or info.get('filename', '')
            if filepath:
                final_filename = filepath

    # Lazily create download directory per thread
    target_dir = _playlist_folder(playlist_title) or DOWNLOAD_DIR
    os.makedirs(target_dir, exist_ok=True)
    filename_prefix = f"{index:03d} - " if playlist_title and index else ""
    outtmpl = os.path.join(target_dir, f'{filename_prefix}%(title)s.%(ext)s')

    ydl_opts = {
        'format': get_format_string(quality),
        'outtmpl': outtmpl,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
        'quiet': True,
        'no_warnings': True,
        'noprogress': False,
        'restrictfilenames': True,  # Prevent OS file path errors
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'overwrites': False,
    }

    if quality == "Audio Only (MP3)":
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        video_url = normalize_video_url(video_id)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

        resolved_filename = _resolve_final_filename(info, final_filename)
        if not resolved_filename:
            raise FileNotFoundError("Download finished but the output file could not be located.")

        # Download + post-processing succeeded
        if not terminal_sent:
            message = {
                "video_id": display_id,
                "status": "done",
                "filename": _relative_download_path(resolved_filename, playlist_title)
            }
            safe_publish(session_id, message, loop)
            terminal_sent = True
            logger.info(f"[{display_id}] Completed: {resolved_filename}")

    except Exception as e:
        logger.error(f"[{display_id}] Download failed: {e}")
        if not terminal_sent:
            message = {
                "video_id": display_id,
                "status": "error",
                "error": str(e)
            }
            safe_publish(session_id, message, loop)
            terminal_sent = True
    finally:
        # Failsafe in case of a crash that bypasses exception blocks
        if not terminal_sent:
            safe_publish(session_id, {
                "video_id": display_id,
                "status": "error",
                "error": "Internal unexpected error"
            }, loop)


def _download_items_from_request(videos: list[str], items: list[DownloadItem] | None) -> list[DownloadItem]:
    if items:
        return sorted(items, key=lambda item: item.index)
    return [
        DownloadItem(id=video_id, title=video_id, index=index)
        for index, video_id in enumerate(videos, start=1)
    ]


async def start_download_task(
    videos: list[str],
    quality: str,
    session_id: str,
    concurrent_count: int,
    playlist_title: str | None = None,
    items: list[DownloadItem] | None = None,
    repair: bool = False,
):
    """Kick off parallel downloads using a thread pool."""
    loop = asyncio.get_event_loop()
    download_items = _download_items_from_request(videos, items)
    if playlist_title:
        _write_playlist_manifest(playlist_title, download_items)
        _reconcile_playlist_files(playlist_title, download_items)
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        futures = [
            loop.run_in_executor(
                executor,
                download_video_sync,
                item.id,
                quality,
                session_id,
                loop,
                playlist_title,
                item.title,
                item.index,
                repair,
            )
            for item in download_items
        ]
        await asyncio.gather(*futures, return_exceptions=True)
    sse_manager.complete_session(session_id)

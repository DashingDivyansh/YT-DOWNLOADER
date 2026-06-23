# 🎬 YouTube Downloader — Master Plan

## 1. Project Goal
Build a **locally-hosted web application** that lets users download individual YouTube videos or entire playlists with full control over quality selection and per-video cherry-picking — all through a premium, visually stunning UI.

---

## 2. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.10+ / **FastAPI** | Async-native, fast, auto-docs via Swagger |
| **Download Engine** | **yt-dlp** | Most actively maintained YouTube extractor; supports playlists, quality filtering, progress hooks |
| **Post-processing** | **ffmpeg** (bundled or system) | Required by yt-dlp to merge separate video+audio streams for high-quality downloads (e.g., 1080p) |
| **Frontend** | Vanilla **HTML + CSS + JavaScript** | Zero build step, instant load, full control over premium aesthetics |
| **Real-time Comms** | **Server-Sent Events (SSE)** | Lightweight one-way push from server → client for live progress; simpler than WebSockets for this use-case |
| **File Serving** | FastAPI `StaticFiles` + `FileResponse` | Serve frontend assets and deliver downloaded files to the browser |

---

## 3. Core Features

### 3.1 Smart URL Detection
- Accept any YouTube URL (video, playlist, or mixed `watch?v=...&list=...`).
- Backend auto-detects type and returns the correct metadata shape.

### 3.2 Metadata Extraction
- **Single video:** title, thumbnail, duration, channel name, available qualities.
- **Playlist:** playlist title, total count, and per-video: title, thumbnail, duration, channel.

### 3.3 Playlist Management UI
- Video cards displayed in a scrollable grid with thumbnails.
- **Select All / Deselect All** toggle button.
- Individual **checkbox** on each video card.
- **Video count badge** showing `X of Y selected`.

### 3.4 Quality Selection
- Global quality dropdown that applies to all selected videos.
- Options: `Best Available`, `1080p`, `720p`, `480p`, `360p`, `Audio Only (MP3)`.
- Backend maps these to yt-dlp format selectors.

### 3.5 Parallel / Concurrent Downloads
- **Configurable concurrency**: User picks how many videos download simultaneously (1–5 workers) via a slider in the UI.
- Backend uses **Python `asyncio` + `concurrent.futures.ThreadPoolExecutor`** to run multiple yt-dlp downloads in parallel.
- Each worker independently reports progress through the shared SSE stream.
- Default: **3 concurrent downloads** — a sweet spot between speed and not hammering YouTube's rate limits.

### 3.6 Download Manager
- Downloads run **server-side** into a configurable output folder (`./downloads/` by default).
- Each video's progress is tracked independently.
- After download completes, user gets a **browser download link** to fetch the file.

### 3.7 Real-time Progress
- SSE stream pushes per-video events: `downloading`, `progress %`, `speed`, `ETA`, `done`, `error`.
- Frontend renders an animated progress bar per video with status text.
- Multiple progress bars animate **simultaneously** when parallel downloads are active.

### 3.8 Error Handling
- Invalid / private / age-restricted video → graceful error card with reason.
- Network failures → retry prompt.
- yt-dlp errors → surfaced as user-friendly messages (not raw tracebacks).
- **One failed download does NOT block the others** — parallel workers are independent.

---

## 4. Project File Structure

```
D:/YT TERMINAL/
├── PLAN.md                  # This plan
├── requirements.txt         # Python dependencies
├── server.py                # FastAPI backend (single file for simplicity)
├── downloads/               # Downloaded files land here
└── frontend/
    ├── index.html           # Main HTML page
    ├── styles.css           # All styling — dark mode, glassmorphism, animations
    └── app.js               # Frontend logic — fetch, render, SSE, download triggers
```

> **Why a single `server.py`?** This is a local utility tool, not a production SaaS. One file keeps it simple to run (`python server.py`) without complex package structures.

---

## 5. API Design

### `POST /api/fetch`
Accepts a YouTube URL, returns metadata.

**Request:**
```json
{ "url": "https://www.youtube.com/watch?v=..." }
```

**Response (single video):**
```json
{
  "type": "video",
  "video": {
    "id": "dQw4w9WgXcQ",
    "title": "...",
    "thumbnail": "https://...",
    "duration": "3:33",
    "channel": "...",
    "qualities": ["1080p", "720p", "480p", "360p", "audio"]
  }
}
```

**Response (playlist):**
```json
{
  "type": "playlist",
  "playlist_title": "My Playlist",
  "videos": [
    { "id": "...", "title": "...", "thumbnail": "...", "duration": "...", "channel": "..." }
  ],
  "qualities": ["1080p", "720p", "480p", "360p", "audio"]
}
```

### `POST /api/download`
Starts downloading selected videos at the chosen quality.

**Request:**
```json
{
  "videos": ["video_id_1", "video_id_2"],
  "quality": "720p",
  "concurrent": 3
}
```

**Response:**
```json
{ "session_id": "abc-123" }
```

### `GET /api/progress/{session_id}`
SSE endpoint. Streams real-time progress events for the download session.

**Event shape:**
```json
{
  "video_id": "dQw4w9WgXcQ",
  "status": "downloading",
  "percent": 45.2,
  "speed": "2.5 MiB/s",
  "eta": "12s"
}
```

### `GET /api/file/{filename}`
Serves a completed download file to the browser.

---

## 6. UI / UX Design Spec

### Theme
- **Dark mode** base (`#0a0a0f` background) with vibrant **purple-cyan gradient** accents.
- **Glassmorphism** panels: semi-transparent backgrounds, blur, subtle borders.
- **Google Font: Inter** for clean, modern typography.

### Layout (Top → Bottom)
1. **Header** — App logo/title with a subtle glow animation.
2. **URL Input Bar** — Large, centered input with a glowing border on focus + "Fetch" button with hover ripple.
3. **Results Section** (appears after fetch):
   - **Playlist header** with title, video count, Select All toggle.
   - **Video card grid** — Each card: thumbnail, title, duration, channel, checkbox. Cards have hover lift + glow effects.
4. **Quality Selector** — Styled dropdown with the quality options.
5. **Concurrency Slider** — Labeled slider (`1×` to `5×`) to set how many videos download in parallel. Shows current value with a tooltip.
6. **Download Button** — Large, gradient-filled CTA with pulse animation.
7. **Progress Section** (appears during download):
   - Per-video progress bars with percentage, speed, ETA.
   - Status badges: `Queued` → `Downloading` → `Done` / `Error`.
   - Multiple bars animate simultaneously based on concurrency setting.
   - **Overall progress** bar at the top: `3 of 12 videos complete`.
8. **Completed Section** — Download links for finished files.

### Animations & Micro-interactions
- Input focus: border glow transition (0.3s ease).
- Video cards: `translateY(-4px)` on hover + box-shadow bloom.
- Buttons: gradient shift on hover, scale down on click.
- Progress bars: smooth `width` transition + shimmer overlay.
- Cards appear with staggered `fadeInUp` animation on load.
- Toast notifications slide in from top-right for errors/success.

---

## 7. Phased Implementation

### Phase 1 — Backend Core ⚙️
1. Create `requirements.txt` with `fastapi`, `uvicorn`, `yt-dlp`.
2. Build `server.py`:
   - `/api/fetch` endpoint using yt-dlp's `extract_info` (no download).
   - `/api/download` endpoint using yt-dlp's download with `progress_hooks` + **ThreadPoolExecutor** for parallel downloads.
   - `/api/progress/{session_id}` SSE endpoint.
   - `/api/file/{filename}` file serving.
   - Mount `frontend/` as static files.
3. Test all endpoints via Swagger UI (`/docs`).

### Phase 2 — Frontend Premium UI 🎨
1. Build `index.html` — semantic structure, all sections.
2. Build `styles.css` — full design system: CSS variables, dark theme, glassmorphism, animations, responsive grid.
3. Build `app.js`:
   - URL fetch → render video cards dynamically.
   - Select All / individual selection logic.
   - Quality dropdown population.

### Phase 3 — Download Flow & Progress 📡
1. Wire up the Download button → `POST /api/download`.
2. Connect to SSE stream → update per-video progress bars in real-time.
3. On completion → show download links.

### Phase 4 — Error Handling & Polish ✨
1. Handle all error states with user-friendly toast notifications.
2. Add loading skeletons while metadata is being fetched.
3. Add input validation (URL format check before hitting the backend).
4. Responsive design for smaller screens.
5. Final visual polish pass.

---

## 8. Prerequisites
- **Python 3.10+** installed and on PATH.
- **ffmpeg** installed and on PATH (required for yt-dlp to merge video+audio streams).
- A modern web browser (Chrome, Edge, Firefox).

---

## 9. How to Run (Final State)
```bash
cd "D:/YT TERMINAL"
pip install -r requirements.txt
python server.py
# Open http://localhost:8000 in your browser
```

---

> **Ready to build?** Approve this plan and we'll start with Phase 1 — setting up the backend.

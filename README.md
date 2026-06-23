<div align="center">
  
# 🎬 YouTube Downloader

<p align="center">
  A premium, locally-hosted web application that lets you download individual YouTube videos or entire playlists with full control over quality and per-video cherry-picking. Built with an asynchronous Python backend and a stunning Glassmorphism UI.
</p>

![UI Preview](https://img.shields.io/badge/UI-Glassmorphism-blueviolet?style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Downloader](https://img.shields.io/badge/Core-yt--dlp-red?style=for-the-badge&logo=youtube&logoColor=white)

</div>

---

## ✨ Features

- **🔗 Smart URL Detection**: Paste any YouTube URL (video or playlist) and the backend will automatically parse the correct metadata.
- **⚡ Parallel Downloads**: Download multiple videos at the same time using asynchronous thread-pool workers. Configure your concurrency level right from the UI!
- **📡 Real-Time Progress**: Powered by Server-Sent Events (SSE), watch beautiful per-video animated progress bars with live speed and ETA updates.
- **🎨 Premium UI/UX**: An immersive dark mode design featuring vibrant gradients, micro-animations, and glassmorphism elements.
- **🎛️ Total Control**: Select specific videos from a playlist and choose your preferred quality (`Best Available`, `1080p`, `720p`, `Audio Only`, etc.).

---

## 🛠️ Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | Python 3.10+ / **FastAPI** | Async-native, lightning fast, auto-generated docs. |
| **Extraction** | **yt-dlp** | The absolute gold standard for video extraction and downloading. |
| **Processing** | **ffmpeg** | Merges separate video/audio streams seamlessly for high-quality downloads. |
| **Frontend** | Vanilla **HTML + CSS + JS** | Zero build step. Complete control over aesthetics. |
| **Real-time** | **Server-Sent Events (SSE)** | Lightweight one-way push from server to client for live progress updates. |

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+** installed on your system.
2. **[FFmpeg](https://ffmpeg.org/download.html)** installed and added to your system's PATH.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DashingDivyansh/YT-DOWNLOADER.git
   cd YT-DOWNLOADER
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python server.py
   # OR run via uvicorn:
   uvicorn app.main:app --reload
   ```

4. **Open your browser:**
   Navigate to `http://localhost:8000` to enjoy the app! Downloads will automatically be saved to the `downloads/` directory.

---

## 💡 How It Works
The app operates by spinning up independent worker threads for each download task. The backend uses `asyncio.run_coroutine_threadsafe` to securely publish progress hooks from the `yt-dlp` thread directly to your browser's SSE stream, bypassing potential thread collision issues.

---

<div align="center">
  <i>Built with ❤️ for a better downloading experience.</i>
</div>

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.api.routes import router

app = FastAPI(title="YouTube Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Important: StaticFiles will serve everything inside frontend directory
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))
os.makedirs(FRONTEND_DIR, exist_ok=True)

@app.get("/api/file/{filename:path}")
async def download_file(filename: str):
    file_path = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
    if os.path.commonpath([DOWNLOAD_DIR, file_path]) != DOWNLOAD_DIR:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if os.path.isfile(file_path):
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    raise HTTPException(status_code=404, detail="File not found")

# Serve UI
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

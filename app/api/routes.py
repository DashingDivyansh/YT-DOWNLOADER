import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from app.models.schemas import FetchRequest, FetchResponse, DownloadRequest, DownloadResponse
from app.services.youtube import fetch_metadata, start_download_task
from app.services.sse_manager import sse_manager

router = APIRouter()

@router.post("/fetch", response_model=FetchResponse)
async def fetch_url(req: FetchRequest):
    try:
        res = await fetch_metadata(req.url)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/download", response_model=DownloadResponse)
async def download_videos(req: DownloadRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())
    sse_manager.create_session(session_id)
    items = req.items or []
    
    # Notify initial queue status
    for vid in [item.id for item in items] or req.videos:
        await sse_manager.publish(session_id, {
            "video_id": vid,
            "status": "queued"
        })
        
    background_tasks.add_task(
        start_download_task,
        req.videos,
        req.quality,
        session_id,
        req.concurrent,
        req.playlist_title,
        items,
        req.repair,
    )
    return DownloadResponse(session_id=session_id)

@router.get("/progress/{session_id}")
async def get_progress(session_id: str):
    return EventSourceResponse(sse_manager.stream_generator(session_id))

from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class FetchRequest(BaseModel):
    url: str

class VideoInfo(BaseModel):
    id: str
    title: str
    thumbnail: str
    duration: str
    channel: str
    index: Optional[int] = None

class FetchResponse(BaseModel):
    type: Literal["video", "playlist"]
    playlist_title: Optional[str] = None
    videos: List[VideoInfo]
    qualities: List[str]

class DownloadItem(BaseModel):
    id: str
    title: str
    index: int = Field(ge=1)

class DownloadRequest(BaseModel):
    videos: List[str]
    quality: str
    concurrent: int = Field(default=3, ge=1, le=5)
    playlist_title: Optional[str] = None
    items: Optional[List[DownloadItem]] = None
    repair: bool = False

class DownloadResponse(BaseModel):
    session_id: str

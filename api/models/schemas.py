"""Pydantic schemas mirroring the Runway API request/response shapes."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ── Task (response) ──────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    id: str
    status: str  # PENDING | THROTTLED | RUNNING | SUCCEEDED | FAILED
    createdAt: Optional[str] = None
    startedAt: Optional[str] = None
    endedAt: Optional[str] = None
    progress: Optional[float] = None
    output: Optional[List[str]] = None  # list of output URLs
    error: Optional[str] = None
    failure: Optional[str] = None

    @classmethod
    def from_orm_task(cls, task) -> "TaskResponse":
        output = None
        if task.status == "SUCCEEDED":
            urls = task.output_urls or ([task.output_url] if task.output_url else [])
            output = urls
        return cls(
            id=str(task.id),
            status=task.status,
            createdAt=task.created_at.isoformat() if task.created_at else None,
            startedAt=task.started_at.isoformat() if task.started_at else None,
            endedAt=task.ended_at.isoformat() if task.ended_at else None,
            progress=task.progress / 100.0 if task.progress is not None else None,
            output=output,
            error=task.error,
        )


# ── Image to Video ────────────────────────────────────────────────────────────

class ImageToVideoRequest(BaseModel):
    model: str = Field(..., description="gen4_turbo | ltx_video | hunyuan_video | cogvideox")
    promptImage: str = Field(..., description="URL or base64 data URI")
    promptText: Optional[str] = Field(None, max_length=1000)
    ratio: Optional[str] = Field("1280:720")
    duration: Optional[int] = Field(5, ge=2, le=10)
    seed: Optional[int] = None
    webhookUrl: Optional[str] = None


# ── Text to Video ─────────────────────────────────────────────────────────────

class TextToVideoRequest(BaseModel):
    model: str = Field(..., description="ltx_video | hunyuan_video")
    promptText: str = Field(..., max_length=1000)
    ratio: Optional[str] = Field("1280:720")
    duration: Optional[int] = Field(5, ge=2, le=10)
    seed: Optional[int] = None
    webhookUrl: Optional[str] = None


# ── Video to Video ────────────────────────────────────────────────────────────

class VideoToVideoRequest(BaseModel):
    model: str = Field("animatediff")
    videoUri: str = Field(...)
    promptText: str = Field(..., max_length=1000)
    references: Optional[List[str]] = None
    seed: Optional[int] = None
    ratio: Optional[str] = None
    webhookUrl: Optional[str] = None


# ── Text / Image to Image ─────────────────────────────────────────────────────

class ReferenceImage(BaseModel):
    uri: str
    tag: Optional[str] = None


class TextToImageRequest(BaseModel):
    model: str = Field(..., description="flux_schnell | flux_dev | sd35_large")
    promptText: str = Field(...)
    ratio: Optional[str] = Field("1024:1024")
    referenceImages: Optional[List[ReferenceImage]] = Field(None, max_items=3)
    seed: Optional[int] = None
    webhookUrl: Optional[str] = None


# ── Character Performance ─────────────────────────────────────────────────────

class CharacterPerformanceRequest(BaseModel):
    model: str = Field("live_portrait")
    character: str = Field(..., description="Image or video URI of character")
    reference: str = Field(..., description="Driving video URI")
    bodyControl: Optional[bool] = True
    expressionIntensity: Optional[int] = Field(3, ge=1, le=5)
    ratio: Optional[str] = None
    seed: Optional[int] = None
    webhookUrl: Optional[str] = None


# ── Text to Speech ────────────────────────────────────────────────────────────

class VoicePreset(BaseModel):
    type: str = "preset"
    presetId: Optional[str] = "default"
    referenceAudio: Optional[str] = None  # for F5-TTS voice cloning


class TextToSpeechRequest(BaseModel):
    model: str = Field("kokoro", description="kokoro | f5_tts")
    promptText: str = Field(...)
    voice: Optional[VoicePreset] = None
    webhookUrl: Optional[str] = None


# ── Speech to Speech ──────────────────────────────────────────────────────────

class SpeechToSpeechRequest(BaseModel):
    model: str = Field("rvc")
    media: str = Field(..., description="Audio or video URI")
    voice: VoicePreset = Field(...)
    removeBackgroundNoise: Optional[bool] = False
    webhookUrl: Optional[str] = None


# ── Sound Effect ──────────────────────────────────────────────────────────────

class SoundEffectRequest(BaseModel):
    model: str = Field("audiocraft_audiogen")
    promptText: str = Field(...)
    duration: Optional[float] = Field(5.0, ge=0.5, le=30.0)
    loop: Optional[bool] = False
    webhookUrl: Optional[str] = None


# ── Voice Isolation ───────────────────────────────────────────────────────────

class VoiceIsolationRequest(BaseModel):
    model: str = Field("demucs")
    audioUri: str = Field(...)
    webhookUrl: Optional[str] = None


# ── Voice Dubbing ─────────────────────────────────────────────────────────────

SUPPORTED_LANGS = [
    "en","hi","pt","zh","es","fr","de","ja","ar","ru","ko","id",
    "it","nl","tr","pl","sv","fil","ms","ro","uk","el","cs","da",
    "fi","bg","hr","sk","ta"
]

class VoiceDubbingRequest(BaseModel):
    model: str = Field("dubbing_pipeline")
    audioUri: str = Field(...)
    targetLang: str = Field(...)
    disableVoiceCloning: Optional[bool] = False
    dropBackgroundAudio: Optional[bool] = False
    numSpeakers: Optional[int] = None
    webhookUrl: Optional[str] = None


# ── Uploads ───────────────────────────────────────────────────────────────────

class UploadRequest(BaseModel):
    filename: str
    type: str = "ephemeral"


class UploadResponse(BaseModel):
    id: str
    uploadUrl: str
    fields: dict
    runwayUri: str

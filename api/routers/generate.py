"""All generation endpoints: image, video, audio, character."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from db.models import Task
from api.auth import get_current_key, require_credits
from api.models.schemas import (
    TaskResponse,
    ImageToVideoRequest, TextToVideoRequest, VideoToVideoRequest,
    TextToImageRequest, CharacterPerformanceRequest,
    TextToSpeechRequest, SpeechToSpeechRequest, SoundEffectRequest,
    VoiceIsolationRequest, VoiceDubbingRequest,
)

router = APIRouter(tags=["generation"])

# Map model names to Celery task names and queues
MODEL_TASK_MAP = {
    # video
    "ltx_video": ("workers.video_worker.generate_video", "video"),
    "hunyuan_video": ("workers.video_worker.generate_video", "video"),
    "cogvideox": ("workers.video_worker.generate_video", "video"),
    "animatediff": ("workers.video_worker.generate_video", "video"),
    # image
    "flux_schnell": ("workers.image_worker.generate_image", "image"),
    "flux_dev": ("workers.image_worker.generate_image", "image"),
    "sd35_large": ("workers.image_worker.generate_image", "image"),
    # audio
    "kokoro": ("workers.audio_worker.text_to_speech", "audio"),
    "f5_tts": ("workers.audio_worker.text_to_speech", "audio"),
    "rvc": ("workers.audio_worker.speech_to_speech", "audio"),
    "audiocraft_audiogen": ("workers.audio_worker.sound_effect", "audio"),
    "demucs": ("workers.audio_worker.voice_isolation", "audio"),
    "dubbing_pipeline": ("workers.audio_worker.voice_dubbing", "audio"),
    # character
    "live_portrait": ("workers.audio_worker.character_performance", "audio"),
}


def _create_task(db, api_key, model: str, endpoint: str, input_data: dict,
                 webhook_url) -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        status="PENDING",
        model=model,
        endpoint=endpoint,
        input=input_data,
        webhook_url=webhook_url,
        api_key_id=str(api_key.id) if api_key else None,
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _enqueue(task: Task):
    task_name, queue = MODEL_TASK_MAP.get(task.model, (None, "image"))
    if not task_name:
        raise HTTPException(status_code=422, detail=f"Unknown model: {task.model}")
    module_path, func_name = task_name.rsplit(".", 1)
    import importlib, threading
    mod = importlib.import_module(module_path)
    celery_task = getattr(mod, func_name)
    # Run in a background thread so the HTTP handler returns immediately.
    # Works without Redis: the task function updates the DB directly.
    t = threading.Thread(
        target=celery_task.apply,
        args=([str(task.id)],),
        daemon=True,
    )
    t.start()


# ── Image to Video ─────────────────────────────────────────────────────────

@router.post("/v1/image_to_video", response_model=TaskResponse, status_code=200)
def image_to_video(
    body: ImageToVideoRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(5)),
):
    task = _create_task(db, api_key, body.model, "image_to_video",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Text to Video ───────────────────────────────────────────────────────────

@router.post("/v1/text_to_video", response_model=TaskResponse, status_code=200)
def text_to_video(
    body: TextToVideoRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(5)),
):
    task = _create_task(db, api_key, body.model, "text_to_video",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Video to Video ──────────────────────────────────────────────────────────

@router.post("/v1/video_to_video", response_model=TaskResponse, status_code=200)
def video_to_video(
    body: VideoToVideoRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(8)),
):
    task = _create_task(db, api_key, body.model, "video_to_video",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Text to Image ───────────────────────────────────────────────────────────

@router.post("/v1/text_to_image", response_model=TaskResponse, status_code=200)
def text_to_image(
    body: TextToImageRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(2)),
):
    task = _create_task(db, api_key, body.model, "text_to_image",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Character Performance ───────────────────────────────────────────────────

@router.post("/v1/character_performance", response_model=TaskResponse, status_code=200)
def character_performance(
    body: CharacterPerformanceRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(5)),
):
    task = _create_task(db, api_key, body.model, "character_performance",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Text to Speech ──────────────────────────────────────────────────────────

@router.post("/v1/text_to_speech", response_model=TaskResponse, status_code=200)
def text_to_speech(
    body: TextToSpeechRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(1)),
):
    task = _create_task(db, api_key, body.model, "text_to_speech",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Speech to Speech ────────────────────────────────────────────────────────

@router.post("/v1/speech_to_speech", response_model=TaskResponse, status_code=200)
def speech_to_speech(
    body: SpeechToSpeechRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(2)),
):
    task = _create_task(db, api_key, body.model, "speech_to_speech",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Sound Effect ────────────────────────────────────────────────────────────

@router.post("/v1/sound_effect", response_model=TaskResponse, status_code=200)
def sound_effect(
    body: SoundEffectRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(2)),
):
    task = _create_task(db, api_key, body.model, "sound_effect",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Voice Isolation ─────────────────────────────────────────────────────────

@router.post("/v1/voice_isolation", response_model=TaskResponse, status_code=200)
def voice_isolation(
    body: VoiceIsolationRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(1)),
):
    task = _create_task(db, api_key, body.model, "voice_isolation",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)


# ── Voice Dubbing ───────────────────────────────────────────────────────────

@router.post("/v1/voice_dubbing", response_model=TaskResponse, status_code=200)
def voice_dubbing(
    body: VoiceDubbingRequest,
    db: Session = Depends(get_db),
    api_key=Depends(require_credits(20)),
):
    task = _create_task(db, api_key, body.model, "voice_dubbing",
                        body.model_dump(), body.webhookUrl)
    _enqueue(task)
    return TaskResponse.from_orm_task(task)

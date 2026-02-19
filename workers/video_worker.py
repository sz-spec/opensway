"""Celery tasks for video generation."""
import os
import logging
import tempfile
from datetime import datetime
from workers.celery_app import celery_app
from db.session import SessionLocal
from db.models import Task
from storage.minio_client import save_bytes

# Ensure bundled ffmpeg is used by imageio
os.environ.setdefault(
    "IMAGEIO_FFMPEG_EXE",
    os.path.join(
        os.path.dirname(__file__), "..", ".venv",
        "lib", "python3.11", "site-packages",
        "imageio_ffmpeg", "binaries", "ffmpeg-macos-aarch64-v7.1",
    ),
)

logger = logging.getLogger(__name__)


def _update_task(task_id, **kwargs):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            db.commit()
    finally:
        db.close()


def _fire_webhook(task):
    if not task.webhook_url:
        return
    import httpx
    try:
        httpx.post(task.webhook_url, json={
            "id": str(task.id),
            "status": task.status,
            "output": task.output_urls or [],
        }, timeout=10)
    except Exception as e:
        logger.warning(f"Webhook failed: {e}")


@celery_app.task(bind=True, name="workers.video_worker.generate_video")
def generate_video(self, task_id: str):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        task.status = "RUNNING"
        task.started_at = datetime.utcnow()
        task.progress = 10
        db.commit()

        inp = task.input
        model_name = inp.get("model", "ltx_video")
        prompt = inp.get("promptText", "")
        prompt_image = inp.get("promptImage")
        ratio = inp.get("ratio", "1280:720")
        duration = inp.get("duration", 5)
        seed = inp.get("seed")

        w, h = (int(x) for x in ratio.split(":")) if ":" in ratio else (1280, 720)
        num_frames = int(duration * 24)  # ~24fps

        from workers.model_loader import get_pool
        pool = get_pool()
        pipe = pool.get(model_name)

        task.progress = 30
        db.commit()

        import torch
        gen = torch.Generator().manual_seed(seed) if seed else None

        kwargs = dict(prompt=prompt, width=w, height=h, num_frames=num_frames, generator=gen)

        if prompt_image:
            from PIL import Image
            import requests, io
            if prompt_image.startswith("data:"):
                import base64
                _, b64 = prompt_image.split(",", 1)
                img = Image.open(io.BytesIO(base64.b64decode(b64)))
            else:
                resp = requests.get(prompt_image, timeout=30)
                img = Image.open(io.BytesIO(resp.content))
            kwargs["image"] = img

        result = pipe(**kwargs)

        task.progress = 80
        db.commit()

        # Export frames to MP4
        frames = result.frames[0]  # list of PIL Images
        filename = f"{task_id}.mp4"
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        import imageio, numpy as np
        writer = imageio.get_writer(tmp_path, fps=24, codec="libx264", quality=7)
        for frame in frames:
            writer.append_data(np.array(frame))
        writer.close()

        with open(tmp_path, "rb") as f:
            video_bytes = f.read()

        url = save_bytes(video_bytes, filename)

        task.status = "SUCCEEDED"
        task.output_url = url
        task.output_urls = [url]
        task.ended_at = datetime.utcnow()
        task.progress = 100
        db.commit()

        _fire_webhook(task)

    except Exception as e:
        logger.exception(f"Video generation failed for task {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()

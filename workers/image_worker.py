"""Celery tasks for image generation."""
import uuid
import logging
from datetime import datetime
from workers.celery_app import celery_app
from db.session import SessionLocal
from db.models import Task, CreditUsage
from storage.minio_client import save_bytes

logger = logging.getLogger(__name__)


def _update_task(task_id: str, **kwargs):
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            db.commit()
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.image_worker.generate_image")
def generate_image(self, task_id: str):
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
        model_name = inp.get("model", "flux_schnell")
        prompt = inp.get("promptText", "")
        ratio = inp.get("ratio", "1024:1024")
        seed = inp.get("seed")

        # Parse ratio
        w, h = (int(x) for x in ratio.split(":")) if ":" in ratio else (1024, 1024)
        # SDXL-Turbo is designed for 512x512; cap to avoid extreme slowness
        is_turbo = "turbo" in model_name or "schnell" in model_name
        if is_turbo:
            w, h = min(w, 512), min(h, 512)
        # Ensure multiples of 8
        w = (w // 8) * 8
        h = (h // 8) * 8

        from workers.model_loader import get_pool
        pool = get_pool()
        pipe = pool.get(model_name)

        task.progress = 30
        db.commit()

        import torch
        gen = torch.Generator().manual_seed(seed) if seed else None
        result = pipe(
            prompt=prompt,
            width=w,
            height=h,
            num_inference_steps=1 if is_turbo else 30,
            guidance_scale=0.0 if is_turbo else 7.5,
            generator=gen,
        )
        image = result.images[0]

        task.progress = 80
        db.commit()

        # Save output
        filename = f"{task_id}.png"
        buf = __import__("io").BytesIO()
        image.save(buf, format="PNG")
        url = save_bytes(buf.getvalue(), filename)

        task.status = "SUCCEEDED"
        task.output_url = url
        task.output_urls = [url]
        task.ended_at = datetime.utcnow()
        task.progress = 100
        db.commit()

        _fire_webhook(task)

    except Exception as e:
        logger.exception(f"Image generation failed for task {task_id}")
        _update_task(task_id,
                     status="FAILED",
                     error=str(e),
                     ended_at=datetime.utcnow())
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
        logger.warning(f"Webhook failed for task {task.id}: {e}")

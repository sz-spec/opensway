import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "")

# Use fakeredis if no Redis server configured (local dev without Redis)
if not REDIS_URL:
    try:
        import fakeredis
        import fakeredis.aioredis
        BROKER_URL = "memory://"
        BACKEND_URL = "cache+memory://"
    except ImportError:
        BROKER_URL = "memory://"
        BACKEND_URL = "cache+memory://"
else:
    BROKER_URL = REDIS_URL
    BACKEND_URL = REDIS_URL

celery_app = Celery(
    "opensway",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=[
        "workers.image_worker",
        "workers.video_worker",
        "workers.audio_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86400,
    task_always_eager=not REDIS_URL,  # run tasks synchronously if no Redis
    task_routes={
        "workers.image_worker.*": {"queue": "image"},
        "workers.video_worker.*": {"queue": "video"},
        "workers.audio_worker.*": {"queue": "audio"},
    },
)

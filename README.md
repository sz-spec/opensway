# OpenSway

**Self-hosted, open source alternative to Runway Gen-4.**
Drop-in compatible API + browser UI. All 17 model families. Runs on Mac (Apple Silicon) and cloud (NVIDIA GPU).

---

## What it does

| Runway Endpoint | OpenSway Model |
|---|---|
| image_to_video | HunyuanVideo 1.5, LTX-Video, CogVideoX |
| text_to_video | HunyuanVideo 1.5, LTX-Video |
| video_to_video | AnimateDiff + ControlNet |
| text_to_image | FLUX.1 [schnell/dev], SD 3.5 Large |
| character_performance | LivePortrait + MuseTalk |
| text_to_speech | Kokoro-82M, F5-TTS |
| speech_to_speech | RVC v2 |
| sound_effect | AudioCraft AudioGen |
| voice_isolation | Demucs v4 |
| voice_dubbing | WhisperX → translate → F5-TTS |

---

## Quick Start (Docker)

```bash
cd docker
docker compose up -d

# Wait for services, then create an API key
curl -X POST http://localhost:8000/v1/admin/keys \
  -H 'Content-Type: application/json' \
  -d '{"name": "default", "credit_balance": 10000}'

# Open UI
open http://localhost:3001
```

## Quick Start (Local Mac)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download models (start with lightweight ones)
bash scripts/download_models.sh image
bash scripts/download_models.sh audio

# 3. Start everything
bash scripts/start-local.sh
```

---

## API Usage (Runway SDK compatible)

```python
from runwayml import RunwayML

# Point SDK at your local server
client = RunwayML(
    api_key="key_your_opensway_key",
    base_url="http://localhost:8000",
)

# Generate image (FLUX.1)
task = client.text_to_image.create(
    model="flux_schnell",
    prompt_text="A mountain lake at sunset, photorealistic",
    ratio="1280:720",
)

# Generate video (LTX-Video)
task = client.image_to_video.create(
    model="ltx_video",
    prompt_image="https://example.com/image.jpg",
    prompt_text="slowly rotating",
    duration=5,
).wait_for_task_output()
```

---

## Architecture

```
Next.js UI → FastAPI → Celery (Redis) → Model Workers → MinIO/local
                ↓
           PostgreSQL (task state)
```

**3 worker queues** (each isolated to its own GPU/CPU budget):
- `image` — FLUX.1, SD 3.5
- `video` — HunyuanVideo, LTX-Video, AnimateDiff
- `audio` — Kokoro, Demucs, AudioCraft, RVC, dubbing pipeline

---

## Models by Hardware

| Model | Mac (MPS) | Cloud (CUDA) | VRAM |
|---|---|---|---|
| FLUX.1 schnell | ✓ | ✓ | 8 GB |
| LTX-Video | ✓ | ✓ | 8 GB |
| Kokoro TTS | ✓ | ✓ | 1 GB |
| Demucs v4 | ✓ (CPU) | ✓ | 4 GB |
| HunyuanVideo | — | ✓ | 14 GB |
| FLUX.1 dev | — | ✓ | 16 GB |
| F5-TTS | ✓ | ✓ | 4 GB |

---

## Directory Structure

```
opensway/
├── api/            FastAPI REST API (15 endpoints)
├── workers/        Celery workers (image / video / audio)
├── backends/       Model inference wrappers
├── db/             SQLAlchemy models + sessions
├── storage/        MinIO / S3 / local file abstraction
├── ui/             Next.js 14 web interface
├── config/         models.yaml + settings.yaml
├── docker/         Dockerfiles + docker-compose.yml
└── scripts/        Model download + startup scripts
```

---

## License

Apache 2.0 — free for commercial use.
Individual model licenses vary — see `config/models.yaml` for details.

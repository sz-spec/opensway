"""Celery tasks for all audio endpoints."""
import logging
import tempfile
from datetime import datetime
from workers.celery_app import celery_app
from db.session import SessionLocal
from db.models import Task
from storage.minio_client import save_bytes

logger = logging.getLogger(__name__)


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


def _save_and_finish(task_id: str, audio_bytes: bytes, ext: str = "wav"):
    filename = f"{task_id}.{ext}"
    url = save_bytes(audio_bytes, filename)
    _update_task(task_id,
                 status="SUCCEEDED",
                 output_url=url,
                 output_urls=[url],
                 ended_at=datetime.utcnow(),
                 progress=100)
    return url


@celery_app.task(bind=True, name="workers.audio_worker.text_to_speech")
def text_to_speech(self, task_id: str):
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
        model_name = inp.get("model", "kokoro")
        text = inp.get("promptText", "")
        voice_cfg = inp.get("voice") or {}

        if model_name == "kokoro":
            import kokoro, soundfile as sf, io
            pipeline = kokoro.KPipeline(lang_code="a")
            voice = voice_cfg.get("presetId", "af_heart")
            generator = pipeline(text, voice=voice, speed=1.0)
            samples, sample_rate = [], 24000
            for _, _, audio in generator:
                samples.append(audio)
            import numpy as np
            full = np.concatenate(samples) if len(samples) > 1 else samples[0]
            buf = io.BytesIO()
            sf.write(buf, full, sample_rate, format="WAV")
            _save_and_finish(task_id, buf.getvalue(), "wav")

        elif model_name == "f5_tts":
            # F5-TTS for voice cloning
            from f5_tts.infer.utils_infer import infer_process, load_model
            import soundfile as sf, io, numpy as np
            ref_audio = voice_cfg.get("referenceAudio")
            # Basic F5-TTS inference
            audio, sr = infer_process(text, ref_audio_path=ref_audio)
            buf = io.BytesIO()
            sf.write(buf, audio, sr, format="WAV")
            _save_and_finish(task_id, buf.getvalue(), "wav")

    except Exception as e:
        logger.exception(f"TTS failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.audio_worker.voice_isolation")
def voice_isolation(self, task_id: str):
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
        audio_uri = inp.get("audioUri")

        # Download audio
        import requests, io, tempfile, soundfile as sf, numpy as np
        resp = requests.get(audio_uri, timeout=60)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        # Demucs separation
        import torch
        from demucs.audio import AudioFile
        from demucs.pretrained import get_model
        from demucs.apply import apply_model

        model = get_model("htdemucs")
        model.eval()

        wav = AudioFile(tmp_path).read(streams=0, samplerate=model.samplerate, channels=model.audio_channels)
        wav = wav.unsqueeze(0)
        with torch.no_grad():
            sources = apply_model(model, wav, device="cpu")

        # sources shape: (batch, stems, channels, samples)
        # stems: drums, bass, other, vocals
        vocals_idx = model.sources.index("vocals")
        vocals = sources[0, vocals_idx]

        buf = io.BytesIO()
        sf.write(buf, vocals.T.numpy(), model.samplerate, format="WAV")
        _save_and_finish(task_id, buf.getvalue(), "wav")

    except Exception as e:
        logger.exception(f"Voice isolation failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.audio_worker.sound_effect")
def sound_effect(self, task_id: str):
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
        prompt = inp.get("promptText", "")
        duration = inp.get("duration", 5.0)

        from audiocraft.models import AudioGen
        from audiocraft.data.audio import audio_write
        import io, soundfile as sf, torch

        model = AudioGen.get_pretrained("facebook/audiogen-medium")
        model.set_generation_params(duration=duration)
        wav = model.generate([prompt])  # shape (1, 1, samples)
        audio = wav[0, 0].cpu().numpy()

        buf = io.BytesIO()
        sf.write(buf, audio, model.sample_rate, format="WAV")
        _save_and_finish(task_id, buf.getvalue(), "wav")

    except Exception as e:
        logger.exception(f"Sound effect failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.audio_worker.voice_dubbing")
def voice_dubbing(self, task_id: str):
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
        from backends.dubbing_pipeline import dub_video

        def progress(pct):
            task.progress = pct
            db.commit()

        wav_bytes = dub_video(
            audio_uri=inp["audioUri"],
            target_lang=inp["targetLang"],
            disable_voice_cloning=inp.get("disableVoiceCloning", False),
            drop_background_audio=inp.get("dropBackgroundAudio", False),
            num_speakers=inp.get("numSpeakers"),
            progress_callback=progress,
        )
        _save_and_finish(task_id, wav_bytes, "wav")
        task = db.query(Task).filter(Task.id == task_id).first()
        _fire_webhook(task)

    except Exception as e:
        logger.exception(f"Voice dubbing failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.audio_worker.character_performance")
def character_performance(self, task_id: str):
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
        from backends.character_performance import animate_with_live_portrait

        def progress(pct):
            task.progress = pct
            db.commit()

        mp4_bytes = animate_with_live_portrait(
            character_uri=inp["character"],
            reference_uri=inp["reference"],
            body_control=inp.get("bodyControl", True),
            expression_intensity=inp.get("expressionIntensity", 3),
            progress_callback=progress,
        )
        _save_and_finish(task_id, mp4_bytes, "mp4")
        task = db.query(Task).filter(Task.id == task_id).first()
        _fire_webhook(task)

    except Exception as e:
        logger.exception(f"Character performance failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()


@celery_app.task(bind=True, name="workers.audio_worker.video_to_video")
def video_to_video(self, task_id: str):
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
        from backends.video_to_video import transform_video

        def progress(pct):
            task.progress = pct
            db.commit()

        mp4_bytes = transform_video(
            video_uri=inp["videoUri"],
            prompt=inp["promptText"],
            references=inp.get("references"),
            seed=inp.get("seed"),
            ratio=inp.get("ratio"),
            progress_callback=progress,
        )
        _save_and_finish(task_id, mp4_bytes, "mp4")
        task = db.query(Task).filter(Task.id == task_id).first()
        _fire_webhook(task)

    except Exception as e:
        logger.exception(f"Video-to-video failed for {task_id}")
        _update_task(task_id, status="FAILED", error=str(e), ended_at=datetime.utcnow())
    finally:
        db.close()

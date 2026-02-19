"""
Voice dubbing pipeline: WhisperX → translate → F5-TTS → Demucs mix.
Supports 29 languages matching Runway's voice_dubbing endpoint.
"""
import os
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import requests
import soundfile as sf

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = [
    "en","hi","pt","zh","es","fr","de","ja","ar","ru","ko","id",
    "it","nl","tr","pl","sv","fil","ms","ro","uk","el","cs","da",
    "fi","bg","hr","sk","ta"
]

# Whisper language codes map (ISO 639-1 → Whisper lang name)
LANG_MAP = {
    "en": "english", "hi": "hindi", "pt": "portuguese", "zh": "chinese",
    "es": "spanish", "fr": "french", "de": "german", "ja": "japanese",
    "ar": "arabic", "ru": "russian", "ko": "korean", "id": "indonesian",
    "it": "italian", "nl": "dutch", "tr": "turkish", "pl": "polish",
    "sv": "swedish", "fil": "filipino", "ms": "malay", "ro": "romanian",
    "uk": "ukrainian", "el": "greek", "cs": "czech", "da": "danish",
    "fi": "finnish", "bg": "bulgarian", "hr": "croatian", "sk": "slovak",
    "ta": "tamil",
}


def _download_media(uri: str) -> tuple[bytes, str]:
    """Download media from URI, return (bytes, suffix)."""
    resp = requests.get(uri, timeout=120)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "video" in content_type:
        suffix = ".mp4"
    elif "audio" in content_type:
        suffix = ".wav"
    else:
        suffix = Path(uri.split("?")[0]).suffix or ".wav"
    return resp.content, suffix


def _extract_audio(video_path: str, out_path: str):
    """Extract audio track from video using ffmpeg."""
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
         "-ar", "44100", "-ac", "2", out_path],
        check=True, capture_output=True
    )


def _transcribe_and_align(audio_path: str, language: str = None) -> list[dict]:
    """
    Run WhisperX: transcribe + word-level alignment.
    Returns list of segments: {text, start, end}.
    """
    import whisperx
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    model = whisperx.load_model("large-v3", device, compute_type=compute_type)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16, language=language)

    # Word-level alignment
    align_model, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    result = whisperx.align(result["segments"], align_model, metadata, audio, device)

    return result["segments"]


def _translate_segments(segments: list[dict], target_lang: str) -> list[dict]:
    """
    Translate segment text to target language.
    Uses a local LLM or falls back to Helsinki-NLP translation models.
    """
    try:
        from transformers import pipeline as hf_pipeline
        # Use Helsinki-NLP/opus-mt models (offline, no API key needed)
        src_lang = segments[0].get("language", "en") if segments else "en"
        model_name = f"Helsinki-NLP/opus-mt-{src_lang}-{target_lang}"
        try:
            translator = hf_pipeline("translation", model=model_name)
        except Exception:
            # Fallback: opus-mt-en-ROMANCE or multilingual
            model_name = "Helsinki-NLP/opus-mt-en-mul"
            translator = hf_pipeline("translation", model=model_name,
                                     tokenizer_kwargs={"tgt_lang": target_lang})

        translated = []
        for seg in segments:
            result = translator(seg["text"], max_length=512)
            translated.append({**seg, "text": result[0]["translation_text"]})
        return translated

    except Exception as e:
        logger.warning(f"Translation failed ({e}), using original text")
        return segments


def _synthesize_segments(segments: list[dict], target_lang: str,
                          ref_audio: Optional[str] = None,
                          sample_rate: int = 24000) -> np.ndarray:
    """
    TTS each segment with Kokoro (fast) or F5-TTS (voice cloning).
    Assembles output at correct timestamps.
    """
    if not segments:
        return np.zeros(sample_rate, dtype=np.float32)

    total_duration = max(s["end"] for s in segments)
    output = np.zeros(int(total_duration * sample_rate), dtype=np.float32)

    if ref_audio:
        # F5-TTS voice cloning
        from f5_tts.infer.utils_infer import infer_process
        for seg in segments:
            try:
                audio, sr = infer_process(seg["text"], ref_audio_path=ref_audio)
                if sr != sample_rate:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
                start_idx = int(seg["start"] * sample_rate)
                end_idx = start_idx + len(audio)
                output[start_idx:min(end_idx, len(output))] += audio[:min(len(audio), len(output) - start_idx)]
            except Exception as e:
                logger.warning(f"F5-TTS segment failed: {e}")
    else:
        # Kokoro TTS (fast, no cloning)
        import kokoro
        lang_code = target_lang[:2] if len(target_lang) >= 2 else "en"
        kokoro_lang = {"en": "a", "zh": "z", "fr": "f", "de": "d",
                       "es": "e", "ja": "j", "ko": "k", "pt": "p"}.get(lang_code, "a")
        pipeline = kokoro.KPipeline(lang_code=kokoro_lang)

        for seg in segments:
            try:
                gen = pipeline(seg["text"], voice="af_heart", speed=1.0)
                chunks = [audio for _, _, audio in gen]
                audio = np.concatenate(chunks) if chunks else np.array([])
                if len(audio) == 0:
                    continue
                start_idx = int(seg["start"] * sample_rate)
                end_idx = start_idx + len(audio)
                output[start_idx:min(end_idx, len(output))] += audio[:min(len(audio), len(output) - start_idx)]
            except Exception as e:
                logger.warning(f"Kokoro segment failed: {e}")

    return output


def _separate_vocals(audio_path: str) -> tuple[np.ndarray, int]:
    """Use Demucs to isolate background audio (everything except vocals)."""
    import torch
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model
    from demucs.apply import apply_model

    model = get_model("htdemucs")
    model.eval()
    wav = AudioFile(audio_path).read(streams=0, samplerate=model.samplerate,
                                     channels=model.audio_channels)
    wav = wav.unsqueeze(0)
    with torch.no_grad():
        sources = apply_model(model, wav, device="cpu")

    # Return everything except vocals (background: drums + bass + other)
    vocals_idx = model.sources.index("vocals")
    bg_indices = [i for i in range(len(model.sources)) if i != vocals_idx]
    background = sum(sources[0, i] for i in bg_indices)
    return background.mean(0).numpy(), model.samplerate


def dub_video(
    audio_uri: str,
    target_lang: str,
    disable_voice_cloning: bool = False,
    drop_background_audio: bool = False,
    num_speakers: Optional[int] = None,
    progress_callback=None,
) -> bytes:
    """
    Full dubbing pipeline. Returns WAV bytes of dubbed audio.

    Steps:
    1. Download source media
    2. Extract audio (if video)
    3. Transcribe + align (WhisperX)
    4. Translate to target language
    5. TTS synthesize (Kokoro or F5-TTS)
    6. Mix with background audio (Demucs)
    7. Return mixed WAV
    """
    if target_lang not in SUPPORTED_LANGS:
        raise ValueError(f"Unsupported target language: {target_lang}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 1. Download
        if progress_callback:
            progress_callback(10)
        media_bytes, suffix = _download_media(audio_uri)
        media_path = str(tmp / f"source{suffix}")
        Path(media_path).write_bytes(media_bytes)

        # 2. Extract audio if video
        audio_path = str(tmp / "audio.wav")
        if suffix in (".mp4", ".mov", ".avi", ".mkv"):
            _extract_audio(media_path, audio_path)
        else:
            Path(audio_path).write_bytes(media_bytes)

        # 3. Transcribe
        if progress_callback:
            progress_callback(25)
        src_lang = None  # auto-detect
        segments = _transcribe_and_align(audio_path, language=src_lang)

        # 4. Translate
        if progress_callback:
            progress_callback(45)
        translated = _translate_segments(segments, target_lang)

        # 5. TTS synthesize
        if progress_callback:
            progress_callback(60)
        ref_audio = audio_path if not disable_voice_cloning else None
        SAMPLE_RATE = 24000
        dubbed_audio = _synthesize_segments(translated, target_lang,
                                            ref_audio=ref_audio,
                                            sample_rate=SAMPLE_RATE)

        # 6. Background mix
        if progress_callback:
            progress_callback(80)
        if not drop_background_audio:
            try:
                bg_audio, bg_sr = _separate_vocals(audio_path)
                if bg_sr != SAMPLE_RATE:
                    import librosa
                    bg_audio = librosa.resample(bg_audio, orig_sr=bg_sr, target_sr=SAMPLE_RATE)
                # Align lengths
                min_len = min(len(dubbed_audio), len(bg_audio))
                mixed = dubbed_audio[:min_len] * 0.85 + bg_audio[:min_len] * 0.35
            except Exception as e:
                logger.warning(f"Background separation failed ({e}), using voice only")
                mixed = dubbed_audio
        else:
            mixed = dubbed_audio

        # 7. Export
        if progress_callback:
            progress_callback(95)
        buf = io.BytesIO()
        sf.write(buf, mixed, SAMPLE_RATE, format="WAV")
        return buf.getvalue()

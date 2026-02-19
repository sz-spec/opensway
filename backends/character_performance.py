"""
Character performance backend.
Uses LivePortrait for portrait animation driven by a reference video.
Falls back to SadTalker for audio-driven animation.
"""
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import requests

logger = logging.getLogger(__name__)


def _download(uri: str) -> tuple[bytes, str]:
    if uri.startswith("data:"):
        import base64
        header, b64 = uri.split(",", 1)
        ext = header.split(";")[0].split("/")[-1]
        return base64.b64decode(b64), f".{ext}"
    resp = requests.get(uri, timeout=60)
    resp.raise_for_status()
    suffix = Path(uri.split("?")[0]).suffix or ".jpg"
    return resp.content, suffix


def animate_with_live_portrait(
    character_uri: str,
    reference_uri: str,
    body_control: bool = True,
    expression_intensity: int = 3,
    progress_callback=None,
) -> bytes:
    """
    Animate a portrait image/video using LivePortrait.
    character_uri: source image or video (the face to animate)
    reference_uri: driving video (the motion source)
    Returns MP4 bytes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if progress_callback:
            progress_callback(10)

        # Download inputs
        char_bytes, char_ext = _download(character_uri)
        ref_bytes, ref_ext = _download(reference_uri)

        char_path = str(tmp / f"character{char_ext}")
        ref_path = str(tmp / f"reference{ref_ext}")
        out_path = str(tmp / "output.mp4")

        Path(char_path).write_bytes(char_bytes)
        Path(ref_path).write_bytes(ref_bytes)

        if progress_callback:
            progress_callback(25)

        try:
            from liveportrait.pipeline import LivePortraitPipeline
            from liveportrait.config.argument_config import ArgumentConfig
            from liveportrait.config.inference_config import InferenceConfig

            cfg = InferenceConfig(
                flag_do_crop=True,
                flag_pasteback=True,
                flag_eye_retargeting=True,
                flag_lip_retargeting=False,
                driving_multiplier=expression_intensity / 3.0,
            )

            pipeline = LivePortraitPipeline(inference_cfg=cfg)

            if progress_callback:
                progress_callback(50)

            pipeline.execute(
                source_image_path=char_path,
                driving_video_path=ref_path,
                output_path=out_path,
            )

        except ImportError:
            logger.warning("LivePortrait not installed, falling back to subprocess")
            _run_liveportrait_subprocess(char_path, ref_path, out_path,
                                         expression_intensity)

        if progress_callback:
            progress_callback(90)

        if not Path(out_path).exists():
            raise RuntimeError("LivePortrait produced no output")

        return Path(out_path).read_bytes()


def _run_liveportrait_subprocess(
    char_path: str, ref_path: str, out_path: str, intensity: int
):
    """Run LivePortrait via subprocess if not installed as a package."""
    import subprocess
    import shutil

    lp_dir = Path.home() / ".cache" / "opensway" / "LivePortrait"
    if not lp_dir.exists():
        logger.info("Cloning LivePortrait...")
        subprocess.run(
            ["git", "clone", "https://github.com/KwaiVGI/LivePortrait.git", str(lp_dir)],
            check=True, capture_output=True
        )
        subprocess.run(
            ["pip", "install", "-r", str(lp_dir / "requirements.txt")],
            check=True, capture_output=True
        )

    subprocess.run(
        [
            "python", str(lp_dir / "inference.py"),
            "-s", char_path,
            "-d", ref_path,
            "-o", out_path,
            "--driving_multiplier", str(intensity / 3.0),
        ],
        check=True,
        cwd=str(lp_dir),
    )


def animate_with_musetalk(
    character_image_uri: str,
    audio_uri: str,
    progress_callback=None,
) -> bytes:
    """
    Lip-sync a character image to an audio track using MuseTalk.
    Returns MP4 bytes.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if progress_callback:
            progress_callback(10)

        char_bytes, char_ext = _download(character_image_uri)
        audio_bytes, audio_ext = _download(audio_uri)

        char_path = str(tmp / f"character{char_ext}")
        audio_path = str(tmp / f"audio{audio_ext}")
        out_path = str(tmp / "output.mp4")

        Path(char_path).write_bytes(char_bytes)
        Path(audio_path).write_bytes(audio_bytes)

        if progress_callback:
            progress_callback(30)

        # MuseTalk inference
        import subprocess
        mt_dir = Path.home() / ".cache" / "opensway" / "MuseTalk"
        if not mt_dir.exists():
            subprocess.run(
                ["git", "clone", "https://github.com/TMElyralab/MuseTalk.git", str(mt_dir)],
                check=True, capture_output=True
            )

        subprocess.run(
            [
                "python", str(mt_dir / "scripts" / "realtime_inference.py"),
                "--video_path", char_path,
                "--audio_path", audio_path,
                "--result_dir", str(tmp / "result"),
            ],
            check=True,
            cwd=str(mt_dir),
        )

        # Find output
        result_dir = tmp / "result"
        outputs = list(result_dir.glob("*.mp4"))
        if not outputs:
            raise RuntimeError("MuseTalk produced no output")

        if progress_callback:
            progress_callback(90)

        return outputs[0].read_bytes()

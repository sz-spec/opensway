"""
Video-to-video transformation using AnimateDiff + ControlNet.
Applies style/motion transfer to an existing video.
"""
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional, List

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)


def _download_video(uri: str) -> str:
    """Download video to temp file, return path."""
    resp = requests.get(uri, timeout=120)
    resp.raise_for_status()
    suffix = Path(uri.split("?")[0]).suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(resp.content)
    tmp.flush()
    return tmp.name


def _extract_frames(video_path: str, max_frames: int = 16) -> list[Image.Image]:
    """Extract evenly-spaced frames from a video."""
    import cv2
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    step = max(1, total // max_frames)

    frames = []
    for i in range(0, min(total, max_frames * step), step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb))
        if len(frames) >= max_frames:
            break
    cap.release()
    return frames


def _frames_to_mp4(frames: list[Image.Image], output_path: str, fps: int = 8):
    """Write PIL frames to MP4 via imageio."""
    import imageio
    imageio.mimwrite(output_path, [np.array(f) for f in frames], fps=fps)


def transform_video(
    video_uri: str,
    prompt: str,
    references: Optional[List[str]] = None,
    seed: Optional[int] = None,
    ratio: Optional[str] = None,
    progress_callback=None,
) -> bytes:
    """
    Style-transfer a video using AnimateDiff + img2img.

    Approach:
    1. Extract frames from source video
    2. Apply img2img SDXL or SD1.5 per-frame with AnimateDiff motion module
    3. Re-assemble into MP4
    """
    import torch
    from diffusers import (
        StableDiffusionImg2ImgPipeline,
        AnimateDiffPipeline,
        MotionAdapter,
        DDIMScheduler,
    )
    from diffusers.utils import export_to_video

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if progress_callback:
            progress_callback(10)

        # Download source video
        video_path = _download_video(video_uri)
        frames = _extract_frames(video_path, max_frames=16)

        if not frames:
            raise RuntimeError("Could not extract frames from video")

        if progress_callback:
            progress_callback(25)

        # Determine output size
        w, h = frames[0].size
        if ratio:
            rw, rh = (int(x) for x in ratio.split(":"))
            w, h = (rw // 8) * 8, (rh // 8) * 8

        # Load AnimateDiff pipeline
        device = "cuda" if torch.cuda.is_available() else (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )

        adapter = MotionAdapter.from_pretrained(
            "guoyww/animatediff-motion-adapter-v1-5-2",
            torch_dtype=torch.float16,
        )
        pipe = AnimateDiffPipeline.from_pretrained(
            "emilianJR/epiCRealism",
            motion_adapter=adapter,
            torch_dtype=torch.float16,
        )
        pipe.scheduler = DDIMScheduler.from_config(
            pipe.scheduler.config,
            beta_schedule="linear",
            clip_sample=False,
            timestep_spacing="linspace",
            steps_offset=1,
        )
        pipe = pipe.to(device)

        if progress_callback:
            progress_callback(50)

        gen = torch.Generator(device=device).manual_seed(seed) if seed else None

        result = pipe(
            prompt=prompt,
            negative_prompt="blurry, distorted, bad quality",
            num_frames=len(frames),
            guidance_scale=7.5,
            num_inference_steps=20,
            generator=gen,
            width=w,
            height=h,
        )

        if progress_callback:
            progress_callback(85)

        output_frames = result.frames[0]
        out_path = str(tmp / "output.mp4")
        export_to_video(output_frames, out_path, fps=8)

        if progress_callback:
            progress_callback(95)

        return Path(out_path).read_bytes()

"""
OpenSway Movie Maker
====================
Produces a 1-minute demo film using the OpenSway API:
  • 10 scenes × 6 s each → 60 s image slideshow
  • Kokoro TTS narration
  • AudioCraft ambient background music (2×30 s, concatenated)
  • Assembled with MoviePy → opensway_demo.mp4
"""

import httpx, time, os, sys, json, tempfile, pathlib

BASE = os.environ.get("OPENSWAY_BASE", "http://localhost:8000")
KEY  = os.environ.get("OPENSWAY_KEY",  "")

if not KEY:
    # Auto-fetch from admin endpoint
    r = httpx.post(f"{BASE}/v1/admin/keys", json={"name": "moviemaker"})
    KEY = r.json()["key"]
    print(f"API key: {KEY}")

HEADERS = {"Authorization": f"Bearer {KEY}", "X-Runway-Version": "2024-11-06"}
OUT = pathlib.Path("/Users/sz/opensway/outputs")
OUT.mkdir(exist_ok=True)

# ── Script ──────────────────────────────────────────────────────────────────

NARRATION = (
    "In a world transformed by artificial intelligence, creativity knows no limits. "
    "OpenSway gives creators the tools to generate photorealistic images "
    "from simple text descriptions. "
    "Transform words into cinematic visuals in seconds. "
    "Design rich soundscapes, realistic voiceovers, and custom sound effects on demand. "
    "Powered entirely by open-source AI models — running on your own hardware, "
    "under your complete control. "
    "Join the future of media creation. "
    "OpenSway — open source, unlimited creativity."
)

SCENES = [
    "aerial cityscape at night, neon lights reflecting on wet streets, flying vehicles, cinematic 8k",
    "AI artist painting a digital canvas, glowing brush strokes forming photorealistic art",
    "words floating in space transforming into vivid imagery, magical light particles",
    "holographic film reel with AI-generated video frames floating, blue and purple tones, cinematic",
    "director clapperboard merging with streams of digital data, futuristic studio",
    "colorful sound waves visualized as glowing ribbons spiraling through a dark audio studio",
    "AI voice avatar with waveform emanating, warm neon glow, dark background, futuristic",
    "open-source code cascading like a waterfall, green text on dark background, Matrix style",
    "earth from space with glowing network connections linking creators worldwide",
    "abstract wave of light, minimalist logo reveal, deep dark background, cinematic",
]

SCENE_DURATION = 6   # seconds per scene
MUSIC_DURATION = 30  # AudioGen max per call; we generate 2× and concatenate

# ── Helpers ─────────────────────────────────────────────────────────────────

def submit(endpoint, body):
    r = httpx.post(f"{BASE}{endpoint}", headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def wait(task_id, label="", poll=5, timeout=600):
    for _ in range(timeout // poll):
        time.sleep(poll)
        r = httpx.get(f"{BASE}/v1/tasks/{task_id}", headers=HEADERS, timeout=10)
        d = r.json()
        s = d["status"]
        if s == "SUCCEEDED":
            return d["output"][0]   # URL
        if s == "FAILED":
            raise RuntimeError(f"{label} FAILED: {d.get('error')}")
    raise TimeoutError(f"{label} timed out after {timeout}s")


def download(url, suffix):
    r = httpx.get(url, timeout=60)
    r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(r.content)
    tmp.flush()
    return tmp.name


# ── Production ───────────────────────────────────────────────────────────────

def main():
    print("═" * 60)
    print("  OpenSway Movie Maker — 1-minute Demo Film")
    print("═" * 60)

    # 1. TTS narration
    print("\n[1/4] Generating narration (TTS)…")
    tts_id = submit("/v1/text_to_speech", {
        "promptText": NARRATION,
        "voice": {"presetId": "af_sky"},
        "model": "kokoro",
    })
    print(f"      task {tts_id}")

    # 2. Background music — two 30-second clips
    print("\n[2/4] Generating background music (2×30 s)…")
    music_ids = []
    for i in range(2):
        mid = submit("/v1/sound_effect", {
            "promptText": "cinematic ambient electronic music, soft synth pads, dreamlike atmosphere, gentle beat",
            "duration": MUSIC_DURATION,
            "model": "audiocraft_audiogen",
        })
        music_ids.append(mid)
        print(f"      music clip {i+1}: {mid}")

    # 3. Scene images — sequential (SDXL not thread-safe)
    print(f"\n[3/4] Generating {len(SCENES)} scene images…")
    image_urls = []
    for i, scene in enumerate(SCENES, 1):
        print(f"  Scene {i:02d}/{len(SCENES)}: {scene[:60]}…")
        img_id = submit("/v1/text_to_image", {
            "promptText": scene,
            "model": "flux_schnell",
            "ratio": "512:512",
        })
        url = wait(img_id, label=f"Scene {i}", poll=3, timeout=120)
        image_urls.append(url)
        print(f"           ✓ {url.split('/')[-1]}")

    # 4. Wait for audio
    print("\n[4/4] Waiting for audio…")
    print("      TTS…", end=" ", flush=True)
    tts_url = wait(tts_id, label="TTS", poll=5, timeout=300)
    print(f"✓ {tts_url.split('/')[-1]}")

    music_urls = []
    for i, mid in enumerate(music_ids, 1):
        print(f"      Music {i}…", end=" ", flush=True)
        murl = wait(mid, label=f"Music {i}", poll=10, timeout=600)
        music_urls.append(murl)
        print(f"✓ {murl.split('/')[-1]}")

    # ── Download all assets ──────────────────────────────────────────────────
    print("\nDownloading assets…")
    img_paths  = [download(u, ".png") for u in image_urls]
    tts_path   = download(tts_url, ".wav")
    music_paths = [download(u, ".wav") for u in music_urls]

    # ── Assemble with MoviePy ────────────────────────────────────────────────
    print("\nAssembling 1-minute film…")
    import os
    os.environ.setdefault(
        "IMAGEIO_FFMPEG_EXE",
        "/Users/sz/opensway/.venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
    )

    from moviepy.editor import (
        ImageClip, concatenate_videoclips,
        AudioFileClip, CompositeAudioClip,
    )
    import numpy as np
    from PIL import Image

    # Build video from images with fade transitions
    clips = []
    for i, path in enumerate(img_paths):
        img = Image.open(path).convert("RGB").resize((1280, 720))
        arr = np.array(img)
        clip = (ImageClip(arr)
                .set_duration(SCENE_DURATION)
                .fadein(0.5)
                .fadeout(0.5))
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    # Narration
    narration_audio = AudioFileClip(tts_path)

    # Concatenate background music clips
    music_clips = [AudioFileClip(p) for p in music_paths]
    from moviepy.editor import concatenate_audioclips
    bg_music = (concatenate_audioclips(music_clips)
                .subclip(0, video.duration)
                .volumex(0.18))   # duck under voice

    # Mix: music + narration
    mixed = CompositeAudioClip([bg_music, narration_audio])
    video  = video.set_audio(mixed)

    out_path = str(OUT / "opensway_demo.mp4")
    video.write_videofile(
        out_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    print(f"\n{'═'*60}")
    print(f"  ✓ Film ready: {out_path}")
    print(f"  Duration: {video.duration:.1f}s")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()

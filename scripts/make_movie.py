"""
OpenSway Movie Maker
====================
Produces a 1-minute demo film using the OpenSway pipeline.

Modes
-----
  --video   (default) LTX-Video clips — real AI-generated motion per scene
  --images            SDXL-Turbo image slideshow — faster fallback

Assets
------
  • 12 scenes × 5 s = 60 s visual track
  • Kokoro TTS narration
  • AudioCraft ambient background music (2 × 30 s, concatenated)
  • Assembled with MoviePy → outputs/opensway_demo.mp4

Usage
-----
  python scripts/make_movie.py            # video mode (LTX-Video)
  python scripts/make_movie.py --images   # image slideshow (fast)
"""

import argparse, httpx, time, os, tempfile, pathlib

# ── Config ───────────────────────────────────────────────────────────────────

BASE = os.environ.get("OPENSWAY_BASE", "http://localhost:8000")
KEY  = os.environ.get("OPENSWAY_KEY",  "")
OUT  = pathlib.Path(os.path.dirname(__file__)).parent / "outputs"
OUT.mkdir(exist_ok=True)

FFMPEG = str(
    pathlib.Path(os.path.dirname(__file__)).parent /
    ".venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
)
os.environ.setdefault("IMAGEIO_FFMPEG_EXE", FFMPEG)

# ── Script ───────────────────────────────────────────────────────────────────

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
    "aerial cityscape at night, neon lights reflecting on wet streets, flying vehicles, cinematic",
    "AI artist painting a glowing digital canvas, colorful brush strokes forming photorealistic art",
    "words floating in space transforming into vivid imagery, magical light particles, motion",
    "holographic film reel with AI-generated frames floating, blue and purple tones, slow rotation",
    "director clapperboard merging with streams of digital data, futuristic studio, dynamic",
    "colorful sound waves visualized as glowing ribbons spiraling through a dark audio studio",
    "AI voice avatar with waveform emanating, warm neon glow, dark background, pulsing",
    "open-source code cascading like a waterfall, green text on dark background, Matrix style",
    "earth from space with glowing network connections linking creators worldwide, slow pan",
    "camera slowly pushing into a glowing OpenSway logo, light rays, cinematic reveal, dark",
    "futuristic media studio interior, holographic screens everywhere, artists at work",
    "abstract particles forming a human face, generative AI art, cinematic, slow motion",
]

SCENE_DURATION = 5    # seconds per scene  (12 × 5 = 60 s)
MUSIC_DURATION = 30   # AudioGen max per call; generate 2× and concatenate

# ── API helpers ───────────────────────────────────────────────────────────────

def get_headers():
    global KEY
    if not KEY:
        r = httpx.post(f"{BASE}/v1/admin/keys", json={"name": "moviemaker"})
        KEY = r.json()["key"]
        print(f"Auto key: {KEY}")
    return {"Authorization": f"Bearer {KEY}", "X-Runway-Version": "2024-11-06"}


def submit(endpoint, body, headers):
    r = httpx.post(f"{BASE}{endpoint}", headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def wait(task_id, label="", headers=None, poll=10, timeout=900):
    for _ in range(timeout // poll):
        time.sleep(poll)
        r = httpx.get(f"{BASE}/v1/tasks/{task_id}", headers=headers, timeout=10)
        d = r.json()
        s = d["status"]
        if s == "SUCCEEDED":
            return d["output"][0]
        if s == "FAILED":
            raise RuntimeError(f"{label} FAILED: {d.get('error','')[:120]}")
    raise TimeoutError(f"{label} timed out after {timeout}s")


def download(url, suffix):
    r = httpx.get(url, timeout=120)
    r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(r.content)
    tmp.flush()
    return tmp.name


# ── MoviePy assembly ──────────────────────────────────────────────────────────

def build_scene_clip_from_video(mp4_path):
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(mp4_path).subclip(0, SCENE_DURATION)
    clip = clip.resize((1280, 720)).fadein(0.4).fadeout(0.4)
    return clip


def build_scene_clip_from_image(png_path):
    from moviepy.editor import ImageClip
    import numpy as np
    from PIL import Image
    img = Image.open(png_path).convert("RGB").resize((1280, 720))
    clip = (ImageClip(np.array(img))
            .set_duration(SCENE_DURATION)
            .fadein(0.4).fadeout(0.4))
    return clip


def assemble(scene_paths, scene_types, tts_path, music_paths, out_path):
    from moviepy.editor import (
        concatenate_videoclips, concatenate_audioclips,
        AudioFileClip, CompositeAudioClip,
    )
    print("\nBuilding scene clips…")
    clips = []
    for i, (path, kind) in enumerate(zip(scene_paths, scene_types), 1):
        print(f"  [{i:02d}/{len(scene_paths)}] {kind}: {pathlib.Path(path).name}")
        if kind == "video":
            clips.append(build_scene_clip_from_video(path))
        else:
            clips.append(build_scene_clip_from_image(path))

    print("Concatenating…")
    video = concatenate_videoclips(clips, method="compose")

    narration = AudioFileClip(tts_path)
    music_clips = [AudioFileClip(p) for p in music_paths]
    bg = (concatenate_audioclips(music_clips)
          .subclip(0, video.duration)
          .volumex(0.18))

    video = video.set_audio(CompositeAudioClip([bg, narration]))

    print(f"Rendering → {out_path}")
    video.write_videofile(
        out_path, fps=24, codec="libx264", audio_codec="aac", logger=None,
    )
    return video.duration


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenSway 1-minute movie maker")
    parser.add_argument("--images", action="store_true",
                        help="Use SDXL image slideshow instead of LTX-Video (faster)")
    args = parser.parse_args()
    use_video = not args.images

    headers = get_headers()
    mode_label = "LTX-Video clips" if use_video else "SDXL image slideshow"

    print("═" * 64)
    print(f"  OpenSway Movie Maker — 1-minute Demo Film")
    print(f"  Mode: {mode_label}")
    print("═" * 64)

    # 1. TTS narration (fire and forget, wait at the end)
    print("\n[1/4] Narration (TTS Kokoro)…")
    tts_id = submit("/v1/text_to_speech", {
        "promptText": NARRATION,
        "voice": {"presetId": "af_sky"},
        "model": "kokoro",
    }, headers)
    print(f"      → {tts_id}")

    # 2. Background music × 2 (fire and forget)
    print("\n[2/4] Background music (2 × 30 s AudioGen)…")
    music_ids = []
    for i in range(2):
        mid = submit("/v1/sound_effect", {
            "promptText": "cinematic ambient electronic music, soft synth pads, dreamlike, gentle beat",
            "duration": MUSIC_DURATION,
            "model": "audiocraft_audiogen",
        }, headers)
        music_ids.append(mid)
        print(f"      clip {i+1} → {mid}")

    # 3. Scenes — sequential (models not concurrent-safe)
    n = len(SCENES)
    scene_urls   = []
    scene_types  = []
    scene_suffix = []

    if use_video:
        print(f"\n[3/4] Generating {n} video clips (LTX-Video, 512×288, 5 s each)…")
        print("      Note: first clip loads the model (~2 min); subsequent clips are faster.")
        for i, scene in enumerate(SCENES, 1):
            print(f"  Scene {i:02d}/{n}: {scene[:62]}…", end=" ", flush=True)
            vid_id = submit("/v1/text_to_video", {
                "promptText": scene,
                "model": "ltx_video",
                "ratio": "512:288",
                "duration": SCENE_DURATION,
            }, headers)
            try:
                url = wait(vid_id, label=f"Scene {i}", headers=headers,
                           poll=10, timeout=900)
                scene_urls.append(url)
                scene_types.append("video")
                scene_suffix.append(".mp4")
                print(f"✓ {url.split('/')[-1]}")
            except Exception as e:
                print(f"✗ video failed ({e}), falling back to image…")
                img_id = submit("/v1/text_to_image", {
                    "promptText": scene,
                    "model": "flux_schnell",
                    "ratio": "512:512",
                }, headers)
                url = wait(img_id, label=f"Scene {i} IMG", headers=headers,
                           poll=5, timeout=120)
                scene_urls.append(url)
                scene_types.append("image")
                scene_suffix.append(".png")
                print(f"  ↳ image ✓ {url.split('/')[-1]}")
    else:
        print(f"\n[3/4] Generating {n} scene images (SDXL-Turbo)…")
        for i, scene in enumerate(SCENES, 1):
            print(f"  Scene {i:02d}/{n}: {scene[:62]}…", end=" ", flush=True)
            img_id = submit("/v1/text_to_image", {
                "promptText": scene,
                "model": "flux_schnell",
                "ratio": "512:512",
            }, headers)
            url = wait(img_id, label=f"Scene {i}", headers=headers, poll=3, timeout=120)
            scene_urls.append(url)
            scene_types.append("image")
            scene_suffix.append(".png")
            print(f"✓ {url.split('/')[-1]}")

    # 4. Wait for audio
    print("\n[4/4] Waiting for audio…")
    print("      TTS…", end=" ", flush=True)
    tts_url = wait(tts_id, label="TTS", headers=headers, poll=5, timeout=300)
    print(f"✓ {tts_url.split('/')[-1]}")

    music_urls = []
    for i, mid in enumerate(music_ids, 1):
        print(f"      Music {i}…", end=" ", flush=True)
        murl = wait(mid, label=f"Music {i}", headers=headers, poll=10, timeout=600)
        music_urls.append(murl)
        print(f"✓ {murl.split('/')[-1]}")

    # Download
    print("\nDownloading assets…")
    scene_paths = [download(u, s) for u, s in zip(scene_urls, scene_suffix)]
    tts_path    = download(tts_url, ".wav")
    music_paths = [download(u, ".wav") for u in music_urls]

    # Assemble
    out_path = str(OUT / "opensway_demo.mp4")
    duration = assemble(scene_paths, scene_types, tts_path, music_paths, out_path)

    print(f"\n{'═'*64}")
    print(f"  ✓ Film ready: {out_path}")
    print(f"  Duration:     {duration:.1f}s")
    print(f"  Scenes:       {sum(1 for t in scene_types if t=='video')} video, "
          f"{sum(1 for t in scene_types if t=='image')} image")
    print(f"{'═'*64}")


if __name__ == "__main__":
    main()

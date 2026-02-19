"""
OpenSway Movie Maker
====================
Produces a demo film using the OpenSway pipeline.

Modes
-----
  --video   (default) LTX-Video clips — real AI-generated motion per scene
  --images            SDXL-Turbo image slideshow — faster fallback

Assets
------
  • 24 scenes × 8 s = 192 s visual track
  • Kokoro TTS narration
  • AudioCraft ambient background music (7 × 30 s, concatenated)
  • Assembled with MoviePy → outputs/opensway_demo_long.mp4

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
    "From the depths of space to the forests of Earth, from ancient ruins to cutting-edge laboratories — "
    "the universe is filled with moments waiting to be captured. "
    "For centuries, telling stories with moving images required vast resources — studios, crews, "
    "expensive equipment, and years of technical training. "
    "But what if anyone could become a filmmaker? "
    "What if the tools to create professional-quality cinematic experiences "
    "were available to every human being on Earth? "
    "OpenSway is making that vision real. "
    "Powered entirely by open-source artificial intelligence, OpenSway gives you the ability to "
    "generate photorealistic video from words. "
    "Describe a volcanic eruption at midnight — you get it. "
    "A ballet dancer in an abandoned theatre — done. "
    "An astronaut floating above Earth — created. "
    "Text becomes imagery. Words become worlds. "
    "But OpenSway is more than video generation. It is a complete creative suite. "
    "Generate rich, immersive soundscapes from text. "
    "Create lifelike voiceovers in any style. "
    "Compose custom background music for any mood. "
    "Isolate vocals from any recording. "
    "Animate portraits with the power of AI. "
    "Every capability that once required an entire production team, "
    "now available through a single API. "
    "And unlike proprietary platforms, OpenSway runs entirely on your own hardware — "
    "your data stays yours, your creativity stays yours, your outputs stay yours. "
    "No subscriptions. No data harvesting. No limits imposed by someone else's business model. "
    "Just pure, unlimited creative power — open source, forever. "
    "The future of storytelling belongs to everyone. "
    "OpenSway."
)

SCENES = [
    # Space / Cosmos
    "vast nebula in deep space, electric purple and teal gas clouds drifting, countless stars twinkling, slow camera drift through cosmic dust, photorealistic, IMAX quality",
    "astronaut floating in zero gravity outside space station, Earth glowing blue below, slow rotation, golden sunlight striking the visor, cinematic close-up",
    "surface of Mars at sunrise, rust-red dunes stretching to the horizon, dust devil spiraling in the distance, NASA rover silhouetted against the dawn light, wide cinematic angle",
    "total solar eclipse viewed from a mountain ridge, corona blazing in sudden darkness, sky deepening to violet, crowd of silhouettes standing in awe, dramatic atmospheric",
    # Nature / Earth
    "ancient sequoia forest at dawn, cathedral light shafts piercing morning mist between towering trunks, ferns glowing emerald, slow upward camera tilt, cinematic",
    "bioluminescent ocean waves crashing on a dark beach at night, electric blue-green glow on wet sand, Milky Way reflected in the water, wide establishing shot",
    "volcanic eruption at night, molten lava river flowing into the ocean, massive steam columns rising, lightning crackling in the ash cloud, dramatic wide angle",
    "aerial view of wildebeest migration crossing a river, ten thousand animals moving, golden dust rising, sweeping bird's-eye tracking shot, wildlife documentary cinematic",
    # Human Creativity / Art
    "sculptor's hands shaping wet clay, extreme close-up, warm studio rim lighting, dust motes drifting, a human face slowly emerging from formless raw material",
    "ballet dancer frozen mid-leap in a sun-drenched abandoned opera house, dust particles drifting, graceful arc, black and white with golden highlights",
    "jazz trumpeter playing in a smoky 1950s New Orleans club, warm amber stage light, condensed breath visible, slow pull-back from close-up, cinematic grain",
    "painter making bold gestural brushstrokes on a twenty-foot canvas, crimson and indigo paint spattering, raw creative energy, slow dolly around the artist",
    # Science / Technology
    "snowflake crystal forming at the molecular scale, hexagonal lattice assembling atom by atom, electron-microscope aesthetic, otherworldly geometric beauty, extreme macro",
    "quantum computer inside a cryogenic cooling chamber, iridescent rainbow reflections on superconducting coils, scientists observing through clean-room glass, sci-fi",
    "deep-sea submarine lighting a hydrothermal vent, ghostly tube worms and albino fish surrounding the beams, pitch-black abyss, ultra-HD underwater cinema",
    "holographic DNA double-helix rotating slowly in a dark laboratory, gene sequences glowing, researcher's face bathed in electric blue, dramatic close-up",
    # Cities / Civilization
    "Hong Kong skyline at golden hour, skyscrapers reflected in Victoria Harbour, neon signs beginning to illuminate, helicopter slowly descending toward the city",
    "Roman Colosseum interior at midnight under the Milky Way, moonlight on ancient marble, owls gliding through stone arches, slow panoramic pan, timeless atmosphere",
    "Japanese bullet train racing through snowy countryside, Mount Fuji on the horizon, cherry blossoms swept in the slipstream, cinematic parallel tracking shot",
    "Istanbul Grand Bazaar at dawn, merchants unveiling colorful silks and spices, shafts of light through ancient domed skylights, low-angle tracking shot",
    # AI and the Future
    "neural network visualization, thousands of glowing nodes firing simultaneously in the dark, synaptic connections forming like constellations, consciousness emerging",
    "solo creator at a desk at 3am, laptop the only light source, AI-generated images and music orbiting them like planets, creative flow made luminous and visible",
    "a human hand and a glowing AI-rendered hand reaching toward each other across a luminous threshold, fingertips almost touching, the boundary between them dissolving",
    "the OpenSway logo assembling from streaming stardust and light particles in deep space, camera slowly pulling back to reveal the full glowing logo, epic cinematic",
]

SCENE_DURATION = 8    # seconds per scene  (24 × 8 = 192 s)
MUSIC_CLIPS    = 7    # 7 × 30 s = 210 s covers full film
MUSIC_DURATION = 30   # AudioGen max per call
VIDEO_RATIO    = "768:432"
OUT_FILENAME   = "opensway_demo_long.mp4"

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


def wait(task_id, label="", headers=None, poll=10, timeout=1200):
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
    clip = clip.resize((1280, 720)).fadein(0.5).fadeout(0.5)
    return clip


def build_scene_clip_from_image(png_path):
    from moviepy.editor import ImageClip
    import numpy as np
    from PIL import Image
    img = Image.open(png_path).convert("RGB").resize((1280, 720))
    clip = (ImageClip(np.array(img))
            .set_duration(SCENE_DURATION)
            .fadein(0.5).fadeout(0.5))
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
          .volumex(0.15))

    video = video.set_audio(CompositeAudioClip([bg, narration]))

    print(f"Rendering → {out_path}")
    video.write_videofile(
        out_path, fps=24, codec="libx264", audio_codec="aac", logger=None,
    )
    return video.duration


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenSway demo film maker")
    parser.add_argument("--images", action="store_true",
                        help="Use SDXL image slideshow instead of LTX-Video (faster)")
    args = parser.parse_args()
    use_video = not args.images

    headers = get_headers()
    mode_label = f"LTX-Video clips {VIDEO_RATIO}" if use_video else "SDXL image slideshow"

    print("═" * 64)
    print(f"  OpenSway Movie Maker — Demo Film")
    print(f"  Mode: {mode_label}")
    print(f"  Scenes: {len(SCENES)} × {SCENE_DURATION}s = {len(SCENES)*SCENE_DURATION}s")
    print("═" * 64)

    # 1. TTS narration (fire and forget, wait at the end)
    print("\n[1/4] Narration (TTS Kokoro)…")
    tts_id = submit("/v1/text_to_speech", {
        "promptText": NARRATION,
        "voice": {"presetId": "af_sky"},
        "model": "kokoro",
    }, headers)
    print(f"      → {tts_id}")

    # 2. Background music (fire and forget)
    print(f"\n[2/4] Background music ({MUSIC_CLIPS} × {MUSIC_DURATION} s AudioGen)…")
    music_ids = []
    for i in range(MUSIC_CLIPS):
        mid = submit("/v1/sound_effect", {
            "promptText": "cinematic ambient orchestral music, sweeping strings, soft synth pads, emotional, dreamlike",
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
        print(f"\n[3/4] Generating {n} video clips (LTX-Video, {VIDEO_RATIO}, {SCENE_DURATION}s each)…")
        print("      Note: first clip loads the model (~2 min); subsequent clips are faster.")
        for i, scene in enumerate(SCENES, 1):
            print(f"  Scene {i:02d}/{n}: {scene[:62]}…", end=" ", flush=True)
            vid_id = submit("/v1/text_to_video", {
                "promptText": scene,
                "model": "ltx_video",
                "ratio": VIDEO_RATIO,
                "duration": SCENE_DURATION,
            }, headers)
            try:
                url = wait(vid_id, label=f"Scene {i}", headers=headers,
                           poll=10, timeout=1200)
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
    out_path = str(OUT / OUT_FILENAME)
    duration = assemble(scene_paths, scene_types, tts_path, music_paths, out_path)

    print(f"\n{'═'*64}")
    print(f"  ✓ Film ready: {out_path}")
    print(f"  Duration:     {duration:.1f}s")
    print(f"  Scenes:       {sum(1 for t in scene_types if t=='video')} video, "
          f"{sum(1 for t in scene_types if t=='image')} image")
    print(f"{'═'*64}")


if __name__ == "__main__":
    main()

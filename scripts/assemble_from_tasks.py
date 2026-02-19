"""
Re-assemble the demo film from already-completed task IDs.
Uses the known task IDs from the previous run to skip re-generation.
"""

import httpx, os, tempfile, pathlib, sys

BASE = os.environ.get("OPENSWAY_BASE", "http://localhost:8000")
KEY  = os.environ.get("OPENSWAY_KEY", "")
OUT  = pathlib.Path(os.path.dirname(__file__)).parent / "outputs"
OUT.mkdir(exist_ok=True)

FFMPEG = str(
    pathlib.Path(os.path.dirname(__file__)).parent /
    ".venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"
)
os.environ.setdefault("IMAGEIO_FFMPEG_EXE", FFMPEG)

# ── Task IDs from the previous run ───────────────────────────────────────────

SCENE_TASK_IDS = [
    "f3964257-428f-48f3-83df-de1e80763eda",
    "5909221d-2706-4fd7-b67a-c3a01df263a8",
    "c69c5cbd-692f-45ba-949e-b3738f7868c5",
    "0e39064b-2449-48d5-94c8-ae15b9dd3fd9",
    "e56a9cb0-3573-4438-924d-33c8f17ce8c5",
    "ea09e516-15f1-4a99-9cc8-049fb47fd7a9",
    "823e546a-2123-4933-b092-bcf00611ff4a",
    "88b2da52-889c-41aa-b1c2-87b97a645b87",
    "dfae7491-b2d4-4ecb-b617-52ec15a38131",
    "6f3d4c5c-d1ae-49ee-af53-2f11d4a11072",
    "68eddc99-d8ad-4174-91a8-5c219419a0d1",
    "e756c4f0-7730-4496-9c3d-c250821c95dc",
]
TTS_TASK_ID    = "1c6611ea-b68f-4576-9f0d-07c76abb09d9"
MUSIC_TASK_IDS = [
    "049afdbd-8513-426e-a3a4-0f652d6ca313",
    "9d883df3-9e02-48bd-9c49-7601e73092b2",
]

SCENE_DURATION = 5

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_headers():
    global KEY
    if not KEY:
        r = httpx.post(f"{BASE}/v1/admin/keys", json={"name": "assembler"})
        KEY = r.json()["key"]
    return {"Authorization": f"Bearer {KEY}", "X-Runway-Version": "2024-11-06"}


def get_output_url(task_id, ext):
    return f"{BASE}/outputs/{task_id}.{ext}"


def download(url, suffix):
    r = httpx.get(url, timeout=120)
    r.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(r.content)
    tmp.flush()
    return tmp.name


# ── Assembly (copied from make_movie.py) ─────────────────────────────────────

def build_scene_clip_from_video(mp4_path):
    from moviepy.editor import VideoFileClip
    clip = VideoFileClip(mp4_path).subclip(0, SCENE_DURATION)
    clip = clip.resize((1280, 720)).fadein(0.4).fadeout(0.4)
    return clip


def assemble(scene_paths, tts_path, music_paths, out_path):
    from moviepy.editor import (
        concatenate_videoclips, concatenate_audioclips,
        AudioFileClip, CompositeAudioClip,
    )
    print("\nBuilding scene clips…")
    clips = []
    for i, path in enumerate(scene_paths, 1):
        print(f"  [{i:02d}/{len(scene_paths)}] {pathlib.Path(path).name}")
        clips.append(build_scene_clip_from_video(path))

    print("Concatenating…")
    video = concatenate_videoclips(clips, method="compose")

    narration   = AudioFileClip(tts_path)
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
    print("Building output URLs…")
    scene_urls = [get_output_url(tid, "mp4") for tid in SCENE_TASK_IDS]
    tts_url    = get_output_url(TTS_TASK_ID, "wav")
    music_urls = [get_output_url(mid, "wav") for mid in MUSIC_TASK_IDS]
    for u in scene_urls + [tts_url] + music_urls:
        print(f"  {u.split('/')[-1]}")

    print("\nDownloading assets…")
    scene_paths = [download(u, ".mp4") for u in scene_urls]
    tts_path    = download(tts_url, ".wav")
    music_paths = [download(u, ".wav") for u in music_urls]

    out_path = str(OUT / "opensway_demo.mp4")
    duration = assemble(scene_paths, tts_path, music_paths, out_path)

    print(f"\n{'═'*64}")
    print(f"  ✓ Film ready: {out_path}")
    print(f"  Duration:     {duration:.1f}s")
    print(f"{'═'*64}")


if __name__ == "__main__":
    main()

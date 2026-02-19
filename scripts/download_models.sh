#!/bin/bash
# Download all model weights to HuggingFace cache
# Run: bash scripts/download_models.sh [category]
# Categories: image | video | audio | all (default: all)

set -e
CATEGORY="${1:-all}"

echo "=== OpenSway Model Download ==="
echo "Category: $CATEGORY"
echo ""

download_model() {
    local repo="$1"
    local desc="$2"
    echo "Downloading: $desc ($repo)"
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('$repo', ignore_patterns=['*.gguf', '*.bin'])
print('Done: $repo')
"
}

if [[ "$CATEGORY" == "image" || "$CATEGORY" == "all" ]]; then
    echo "--- Image Models ---"
    download_model "black-forest-labs/FLUX.1-schnell" "FLUX.1 Schnell (fast, Apache 2.0)"
    # Uncomment for FLUX dev (non-commercial):
    # download_model "black-forest-labs/FLUX.1-dev" "FLUX.1 Dev (quality)"
    download_model "stabilityai/stable-diffusion-3.5-large" "SD 3.5 Large"
fi

if [[ "$CATEGORY" == "video" || "$CATEGORY" == "all" ]]; then
    echo "--- Video Models ---"
    download_model "Lightricks/LTX-Video" "LTX-Video (fast, Apple Silicon)"
    # Large model — uncomment when cloud GPU available:
    # download_model "tencent/HunyuanVideo" "HunyuanVideo 1.5 (quality, 14GB VRAM)"
    download_model "zai-org/CogVideoX-5b" "CogVideoX 5B"
fi

if [[ "$CATEGORY" == "audio" || "$CATEGORY" == "all" ]]; then
    echo "--- Audio Models ---"
    download_model "hexgrad/Kokoro-82M" "Kokoro TTS (fast, MPS-compatible)"
    download_model "facebook/audiogen-medium" "AudioCraft AudioGen"
    # Demucs downloads automatically on first use
    python3 -c "from demucs.pretrained import get_model; get_model('htdemucs'); print('Demucs htdemucs: done')"
fi

if [[ "$CATEGORY" == "character" || "$CATEGORY" == "all" ]]; then
    echo "--- Character Models ---"
    download_model "KwaiVGI/LivePortrait" "LivePortrait"
fi

echo ""
echo "=== All requested models downloaded ==="

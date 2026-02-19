"""VRAM-aware LRU model pool. Loads/unloads models to fit available memory."""
import os
import sys
import logging
from collections import OrderedDict
from typing import Any, Optional
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


def _load_model_registry() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f).get("models", {})


def _detect_device() -> str:
    backend = os.environ.get("DEVICE_BACKEND", "auto")
    if backend != "auto":
        return backend
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _detect_vram_gb() -> float:
    device = _detect_device()
    try:
        if device == "cuda":
            import torch
            return torch.cuda.get_device_properties(0).total_memory / 1e9
        elif device == "mps":
            # Apple unified memory — use env var or default 16GB
            return float(os.environ.get("VRAM_GB", "16"))
    except Exception:
        pass
    return 8.0


class ModelPool:
    def __init__(self):
        self.registry = _load_model_registry()
        self.device = _detect_device()
        self.available_vram = _detect_vram_gb()
        self.used_vram = 0.0
        self._pool: OrderedDict[str, Any] = OrderedDict()

        logger.info(f"ModelPool: device={self.device}, vram={self.available_vram:.1f}GB")

    def _model_vram(self, model_name: str) -> float:
        return self.registry.get(model_name, {}).get("vram_gb", 4.0)

    def _evict_lru(self, needed_gb: float):
        while self.used_vram + needed_gb > self.available_vram and self._pool:
            name, model = self._pool.popitem(last=False)  # remove oldest
            logger.info(f"Evicting model: {name}")
            self._unload(name, model)
            self.used_vram -= self._model_vram(name)
            self.used_vram = max(0.0, self.used_vram)

    def _unload(self, name: str, model: Any):
        try:
            import torch, gc
            del model
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:
            logger.warning(f"Unload error for {name}: {e}")

    def get(self, model_name: str) -> Any:
        if model_name in self._pool:
            # Move to end (most recently used)
            self._pool.move_to_end(model_name)
            return self._pool[model_name]

        needed = self._model_vram(model_name)
        self._evict_lru(needed)

        logger.info(f"Loading model: {model_name}")
        model = self._load(model_name)
        self._pool[model_name] = model
        self.used_vram += needed
        return model

    def _load(self, model_name: str) -> Any:
        # Dispatch to per-model loader
        loaders = {
            "flux_schnell": self._load_flux_schnell,
            "flux_dev": self._load_flux_dev,
            "kokoro": self._load_kokoro,
            "demucs": self._load_demucs,
            "ltx_video": self._load_ltx_video,
            "hunyuan_video": self._load_hunyuan_video,
        }
        loader = loaders.get(model_name)
        if loader is None:
            raise ValueError(f"No loader registered for model: {model_name}")
        return loader()

    # ── Per-model loaders (lazy imports) ────────────────────────────────────

    def _load_flux_schnell(self):
        # SDXL-Turbo: ungated Apache-2.0, ~4GB fp16
        # Set PYTORCH_ENABLE_MPS_FALLBACK=1 to allow unsupported ops to fall to CPU
        from diffusers import StableDiffusionXLPipeline
        import torch
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/sdxl-turbo",
            torch_dtype=torch.float16,
            variant="fp16",
        )
        pipe = pipe.to(self.device)
        pipe.enable_attention_slicing()
        return pipe

    def _load_flux_dev(self):
        # SDXL base for higher quality (also ungated)
        from diffusers import StableDiffusionXLPipeline
        import torch
        dtype = torch.float32 if self.device == "mps" else torch.float16
        kwargs = {} if self.device == "mps" else {"variant": "fp16"}
        pipe = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=dtype,
            **kwargs,
        )
        pipe = pipe.to(self.device)
        pipe.enable_attention_slicing()
        return pipe

    def _load_kokoro(self):
        import kokoro
        model = kokoro.KPipeline(lang_code="a")
        return model

    def _load_demucs(self):
        from demucs.pretrained import get_model
        model = get_model("htdemucs")
        model = model.to(self.device)
        return model

    def _load_ltx_video(self):
        from diffusers import LTXPipeline
        import torch
        pipe = LTXPipeline.from_pretrained(
            "Lightricks/LTX-Video",
            torch_dtype=torch.bfloat16,
        )
        pipe = pipe.to(self.device)
        return pipe

    def _load_hunyuan_video(self):
        from diffusers import HunyuanVideoPipeline
        import torch
        pipe = HunyuanVideoPipeline.from_pretrained(
            "tencent/HunyuanVideo",
            torch_dtype=torch.bfloat16,
        )
        pipe = pipe.to(self.device)
        return pipe


# Singleton pool (per-worker process)
_pool: Optional[ModelPool] = None


def get_pool() -> ModelPool:
    global _pool
    if _pool is None:
        _pool = ModelPool()
    return _pool

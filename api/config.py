import os
import yaml
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=1)
def get_settings() -> dict:
    with open(CONFIG_DIR / "settings.yaml") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_models() -> dict:
    with open(CONFIG_DIR / "models.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("models", {})


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://opensway:opensway@localhost:5432/opensway")
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./outputs")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000/outputs")

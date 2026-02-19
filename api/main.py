"""OpenSway — Open Source Runway Gen-4 compatible API."""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import tasks, organization, uploads, generate, admin

app = FastAPI(
    title="OpenSway",
    description="Open source Runway Gen-4 compatible media generation API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(generate.router)
app.include_router(tasks.router)
app.include_router(organization.router)
app.include_router(uploads.router)
app.include_router(admin.router)

# Serve local output files
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "./outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.on_event("startup")
def on_startup():
    from db.session import init_db
    init_db()
    # Pre-warm transformers lazy imports in the main thread so that
    # background task threads don't hit import-order race conditions.
    try:
        from transformers import (
            CLIPImageProcessor, CLIPTokenizer,
            CLIPTextModel, RobertaTokenizer, T5Tokenizer,
        )
    except Exception:
        pass  # non-fatal — models will load on first use


@app.get("/health")
def health():
    return {"status": "ok", "service": "opensway"}


@app.get("/")
def root():
    return {
        "service": "OpenSway",
        "version": "1.0.0",
        "docs": "/docs",
        "compatible_with": "Runway Gen-4 API (2024-11-06)",
    }

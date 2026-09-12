"""
FastAPI application entrypoint.
Configures CORS, mounts all routers, and manages session lifecycle via lifespan context.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_config import setup_logging, get_logger
from app.sessions.manager import session_manager
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router

# Setup structured JSON logging before anything else runs
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown tasks."""
    logger.info(
        "Starting Real-Time Avatar Backend",
        extra={"event": "startup", "environment": settings.environment},
    )
    await session_manager.start()
    yield
    logger.info("Shutting down", extra={"event": "shutdown"})
    await session_manager.stop()


app = FastAPI(
    title="Real-Time 2D AI Avatar API",
    description="Microservice for real-time avatar generation and streaming via WebSocket.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS — allow any frontend to connect during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles

from app.api.conversation import router as conversation_router

# Mount routers
app.include_router(sessions_router)
app.include_router(websocket_router)
app.include_router(conversation_router)

# Mount demo page, assets, and SDK dist
base_dir = os.path.dirname(os.path.dirname(__file__))
demo_dir = os.path.join(base_dir, "demo")
assets_dir = os.path.join(demo_dir, "assets")
sdk_dist_dir = os.path.join(base_dir, "sdk", "dist")

if os.path.exists(demo_dir):
    app.mount("/demo", StaticFiles(directory=demo_dir, html=True), name="demo")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
if os.path.exists(sdk_dist_dir):
    app.mount("/sdk", StaticFiles(directory=sdk_dist_dir), name="sdk")


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Returns service status and number of active sessions.
    """
    active_count = await session_manager.get_active_count()
    return {
        "status": "ok",
        "environment": settings.environment,
        "tts_provider": settings.tts_provider,
        "active_sessions": active_count,
        "max_sessions": settings.max_concurrent_sessions,
    }

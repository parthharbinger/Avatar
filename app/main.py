"""
FastAPI application entrypoint.
Configures CORS, mounts all routers, and manages session lifecycle via lifespan context.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.logging_config import setup_logging, get_logger
from app.sessions.manager import session_manager
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router
from app.api.conversation import router as conversation_router
from app.api.heygen_video import router as heygen_video_router

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

    # Pretty-printed clickable terminal banner with all URLs
    host_url = f"http://localhost:{settings.port}"
    banner = f"""
======================================================================
  🤖 REAL-TIME INTERACTIVE AI AVATAR PLATFORM
======================================================================
  👉 Interactive Live Demo:    {host_url}/demo/
  👉 Apex Travel Demo Client:  http://localhost:5173/
  👉 Swagger API Docs:         {host_url}/docs
  👉 ReDoc Documentation:      {host_url}/redoc
  👉 Health Check:             {host_url}/health
  👉 OpenAPI JSON Schema:      {host_url}/openapi.json
======================================================================
  🎬 Active Avatar Provider:   {settings.avatar_provider.upper()}
  🎙️ TTS Voice Engine:        {settings.edge_tts_voice} ({settings.tts_provider})
======================================================================
"""
    print(banner, flush=True)

    yield
    logger.info("Shutting down", extra={"event": "shutdown"})
    await session_manager.stop()


app = FastAPI(
    title="Real-Time Interactive AI Avatar Platform",
    description="Microservice for real-time interactive avatar video streaming (D-ID, Simli, Anam.ai, Akool, HeyGen) and 2D neural canvas.",
    version="1.0.0",
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

# Mount routers
app.include_router(sessions_router)
app.include_router(websocket_router)
app.include_router(conversation_router)
app.include_router(heygen_video_router)

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


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root path directly to interactive demo UI."""
    return RedirectResponse(url="/demo/")


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

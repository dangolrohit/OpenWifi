"""FastAPI application entry point for WiFiRouter V2."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from .core.config import settings
from .core.security import hash_password
from .db.session import init_db, AsyncSessionLocal
from .models.user import User
from .services.guest_service import GuestService
from .services.analytics_service import AnalyticsService
from .api.v1.router import api_router
from .websocket.connection_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [wifirouter-api] %(message)s"
)
logger = logging.getLogger("wifirouter.main")

async def background_telemetry_loop():
    """Background task recording bandwidth telemetry every 30 seconds."""
    while True:
        try:
            await asyncio.sleep(30)
            async with AsyncSessionLocal() as db:
                await AnalyticsService.record_sample(db)
        except Exception as exc:
            logger.debug(f"Telemetry record iteration skipped: {exc}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    logger.info("Initializing WiFiRouter database...")
    await init_db()

    # Ensure initial super_admin account exists
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.username == settings.DEFAULT_ADMIN_USER)
        res = await db.execute(stmt)
        admin = res.scalar_one_or_none()
        if not admin:
            logger.info(f"Creating default administrator account: {settings.DEFAULT_ADMIN_USER}")
            admin_user = User(
                username=settings.DEFAULT_ADMIN_USER,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
                role="super_admin",
                is_active=True
            )
            db.add(admin_user)
            await db.commit()

        # Seed default hotspot plans
        await GuestService.get_plans(db)

    # Launch background telemetry recorder
    telemetry_task = asyncio.create_task(background_telemetry_loop())

    yield

    # Shutdown
    telemetry_task.cancel()
    logger.info("WiFiRouter API stopped.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Real-time WebSocket Endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive ping/pong
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

# Locate frontend production build (in-container or local workspace)
dist_dir = Path("/app/frontend/dist")
if not dist_dir.exists():
    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if dist_dir.exists() and (dist_dir / "index.html").exists():
    @app.exception_handler(404)
    async def spa_404_handler(request: Request, exc: Exception):
        """SPA fallback: serve index.html for client-side navigation."""
        if not request.url.path.startswith("/api/"):
            index_path = dist_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")


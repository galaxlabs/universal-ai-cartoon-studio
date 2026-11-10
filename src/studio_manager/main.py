from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.trustedhost import TrustedHostMiddleware

from studio_manager import __version__
from studio_manager.api import router as api_router
from studio_manager.api_v1 import router as api_v1_router
from studio_manager.backup_service import BackupService
from studio_manager.config import PROJECT_ROOT, Settings, default_settings
from studio_manager.database import create_database_engine, database_health, upgrade_database
from studio_manager.import_service import Phase02ImportService
from studio_manager.mcp_gateway import MCPGateway
from studio_manager.mcp_manager import MCPManager
from studio_manager.phase03a_service import Phase03AService
from studio_manager.service import DomainError, StudioService
from studio_manager.storage_service import LocalStorageService
from studio_manager.ui import router as ui_router

TEMPLATES = Jinja2Templates(directory=str(PROJECT_ROOT / "src" / "studio_manager" / "templates"))


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings or default_settings()
    active.validate()
    engine = create_database_engine(active.database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        upgrade_database(active.database_path)
        database_health(engine)
        yield
        engine.dispose()

    app = FastAPI(
        title="Universal AI Cartoon Studio",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    allowed_hosts = [active.host, "localhost"]
    if active.test_mode:
        allowed_hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "src" / "studio_manager" / "static")), name="static")
    app.state.settings = active
    app.state.engine = engine
    app.state.service = StudioService(engine)
    app.state.phase03a = Phase03AService(engine)
    app.state.phase03a_importer = Phase02ImportService(
        engine,
        LocalStorageService(active.project_root / "storage" / "80_REPORTS"),
    )
    app.state.phase03a_backups = BackupService(
        engine,
        active.database_path,
        active.project_root / "storage" / "60_BACKUPS" / "phase03a",
        active.project_root / "storage" / "20_TEMP" / "recovery",
    )
    app.state.mcp = MCPManager(engine)
    app.state.mcp_gateway = MCPGateway(engine)
    app.include_router(api_router)
    app.include_router(api_v1_router)
    app.include_router(ui_router)

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.headers.get("X-Studio-Request") != "1":
            return JSONResponse(status_code=403, content={"error": "missing Studio request header"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard(request: Request) -> HTMLResponse:
        health = database_health(engine)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={"health": health, "version": __version__},
        )

    @app.get("/api/health", include_in_schema=False)
    async def health() -> dict[str, object]:
        database = database_health(engine)
        return {
            "application": "universal-ai-cartoon-studio",
            "project_id": sha256(str(PROJECT_ROOT.resolve()).casefold().encode()).hexdigest()[:16],
            "status": "ok" if database["ok"] else "degraded",
            "version": __version__,
            "bind_host": active.host,
            "database": database,
        }

    return app


app = create_app()

"""FastAPI application assembly and process lifecycle."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src import models  # noqa: F401 - registers SQLAlchemy models with Base
from src.db.config import Base, Settings, get_settings
from src.db.database import engine
from src.logging_config import configure_logging
from src.middleware import RequestContextMiddleware
from src.routers.auth import router as auth_router
from src.routers.ingestion import router as ingestion_router
from src.routers.search import router as search_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the API application."""
    app_settings = settings or get_settings()
    configure_logging(app_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Development can bootstrap tables for convenience. Production uses
        # versioned Alembic migrations before application startup.
        if app_settings.AUTO_CREATE_TABLES:
            Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    docs_url = None if app_settings.is_production or not app_settings.ENABLE_API_DOCS else "/docs"
    redoc_url = None if docs_url is None else "/redoc"
    openapi_url = None if docs_url is None else "/openapi.json"
    application = FastAPI(
        title="AI Image Classifier API",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.add_middleware(
        RequestContextMiddleware,
        request_id_header=app_settings.REQUEST_ID_HEADER,
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=app_settings.trusted_hosts,
    )
    if app_settings.FORCE_HTTPS:
        application.add_middleware(HTTPSRedirectMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router)
    application.include_router(ingestion_router)
    application.include_router(search_router)

    @application.get("/health/live", tags=["health"], include_in_schema=False)
    def liveness_check() -> dict[str, str]:
        """Report that the application process can serve requests."""
        return {"status": "ok"}

    def database_readiness_response() -> JSONResponse:
        """Report whether the required Postgres dependency is reachable."""
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(status_code=200, content={"status": "ok"})

    application.get("/health", tags=["health"])(database_readiness_response)
    application.get("/health/ready", tags=["health"], include_in_schema=False)(
        database_readiness_response
    )

    return application

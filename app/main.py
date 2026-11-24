import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging.config import dictConfig
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings, get_settings
from app.db.session import make_engine

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    retryable: bool
    message: str


class RequestLoggingMiddleware:
    """Log IDs, methods, status and timing; exclude paths, bodies and credentials."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4().hex
        started = perf_counter()
        status = 500

        async def send_response(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        finally:
            logger.info(
                "request_completed request_id=%s method=%s status=%s duration_ms=%.2f",
                request_id,
                scope["method"],
                status,
                (perf_counter() - started) * 1000,
            )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}
                },
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "formatter": "standard"}
                },
                "root": {"handlers": ["console"], "level": settings.log_level},
            }
        )
        app.state.engine = make_engine(settings)
        try:
            yield
        finally:
            app.state.engine.dispose()

    app = FastAPI(title="Customer Support Resolution", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/ready", response_model=HealthResponse, responses={503: {"model": ErrorResponse}})
    def ready(request: Request) -> HealthResponse | JSONResponse:
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("database_unavailable")
            error = ErrorResponse(
                error_code="DATABASE_UNAVAILABLE",
                retryable=True,
                message="Database is unavailable",
            )
            return JSONResponse(status_code=503, content=error.model_dump())
        return HealthResponse(status="ready")

    return app

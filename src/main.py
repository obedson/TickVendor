"""FastAPI application factory and ASGI entry point."""

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.admin import router as admin_router
from src.api.attendance import router as attendance_router
from src.api.auth import router as auth_router
from src.api.communities import router as communities_router
from src.api.events import router as events_router
from src.api.notifications import router as notifications_router
from src.api.payments import router as payments_router
from src.api.profiles import router as profiles_router
from src.api.search import router as search_router
from src.api.tasks import router as tasks_router
from src.api.tickets import router as tickets_router
from src.config import settings
from src.logging_config import configure_logging, request_id_context
from src.security_middleware import rate_limiter, request_key


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    application = FastAPI(title=settings.app_name, debug=settings.debug, version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(admin_router, prefix=settings.api_v1_prefix)
    application.include_router(attendance_router, prefix=settings.api_v1_prefix)
    application.include_router(communities_router, prefix=settings.api_v1_prefix)
    application.include_router(events_router, prefix=settings.api_v1_prefix)
    application.include_router(notifications_router, prefix=settings.api_v1_prefix)
    application.include_router(payments_router, prefix=settings.api_v1_prefix)
    application.include_router(profiles_router, prefix=settings.api_v1_prefix)
    application.include_router(search_router, prefix=settings.api_v1_prefix)
    application.include_router(tickets_router, prefix=settings.api_v1_prefix)
    application.include_router(tasks_router, prefix=settings.api_v1_prefix)

    @application.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        try:
            rate_limiter.check(request_key(request))
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(self), camera=(self)"
            return response
        finally:
            request_id_context.reset(token)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request contains invalid data.",
                    "details": exc.errors(),
                }
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("tickeven.errors").exception(
            {"event": "unhandled_error", "path": request.url.path}, exc_info=exc
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
        )

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/validate", include_in_schema=False)
    async def validation_probe(value: Annotated[int, Query(ge=1)]) -> dict[str, int]:
        return {"value": value}

    return application


app = create_app()
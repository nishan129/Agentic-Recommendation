"""
Custom application exceptions and their FastAPI exception handlers.

All handlers respond with the consistent envelope:
    {"success": false, "message": "...", "error_code": "..."}
and never leak stack traces or raw DB errors to the client.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for all handled application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "APP_ERROR"

    def __init__(self, message: str, error_code: str | None = None, status_code: int | None = None):
        self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class DuplicateError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "DUPLICATE_RESOURCE"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTHENTICATION_FAILED"


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "NOT_AUTHORIZED"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "VALIDATION_ERROR"


def _envelope(message: str, error_code: str) -> dict:
    return {"success": False, "message": message, "error_code": error_code}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.message, exc.error_code),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(str(exc.detail), "HTTP_ERROR"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("Invalid request data", "VALIDATION_ERROR"),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.warning("Integrity error on %s: %s", request.url.path, exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_envelope("Resource already exists or violates a constraint", "INTEGRITY_ERROR"),
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(request: Request, exc: SQLAlchemyError):
        logger.error("Database error on %s: %s", request.url.path, exc.__class__.__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("A database error occurred", "DATABASE_ERROR"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("An unexpected error occurred", "INTERNAL_ERROR"),
        )

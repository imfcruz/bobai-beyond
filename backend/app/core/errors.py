"""
Exceções customizadas e handlers de erro da aplicação.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status
import structlog

logger = structlog.get_logger(__name__)


class AppError(Exception):
    """Erro base da aplicação."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str | int | None = None):
        msg = f"{resource} not found" if resource_id is None else f"{resource} '{resource_id}' not found"
        super().__init__(msg, status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class SecurityGatewayError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "Application error",
        path=request.url.path,
        status_code=exc.status_code,
        message=exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "status_code": 500},
    )

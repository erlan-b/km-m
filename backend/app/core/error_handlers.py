import logging
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import detect_request_language, translate_text

logger = logging.getLogger(__name__)


def build_error_payload(code: str, message: str, detail: Any) -> dict[str, Any]:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
        "detail": detail,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
        language = detect_request_language(request)
        detail = exc.detail
        if isinstance(detail, str):
            detail = translate_text(detail, language)
        message = detail if isinstance(detail, str) else translate_text("Request failed", language)
        payload = build_error_payload(
            code=f"HTTP_{exc.status_code}",
            message=message,
            detail=detail,
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError) -> JSONResponse:
        language = detect_request_language(request)
        payload = build_error_payload(
            code="VALIDATION_ERROR",
            message=translate_text("Request validation failed", language),
            detail=exc.errors(),
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception) -> JSONResponse:
        language = detect_request_language(request)
        logger.exception("Unhandled server exception", exc_info=exc)
        payload = build_error_payload(
            code="INTERNAL_SERVER_ERROR",
            message=translate_text("Internal server error", language),
            detail=translate_text("Internal server error", language),
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)
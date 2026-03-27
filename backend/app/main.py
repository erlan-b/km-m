from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware, build_default_rate_limit_rules

settings = get_settings()
app = FastAPI(title=settings.app_name)

register_exception_handlers(app)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts,
)
app.add_middleware(
    GZipMiddleware,
    minimum_size=settings.gzip_minimum_size,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
    allow_credentials=settings.cors_allow_credentials,
)
app.add_middleware(
    RateLimitMiddleware,
    rules=build_default_rate_limit_rules(settings),
    enabled=settings.enable_rate_limit,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}

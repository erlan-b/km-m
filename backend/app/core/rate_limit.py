from collections import deque
from dataclasses import dataclass
import hashlib
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.error_handlers import build_error_payload


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    path_prefixes: tuple[str, ...]
    methods: tuple[str, ...]
    max_requests: int
    window_seconds: int


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check_and_mark(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= max_requests:
                oldest = bucket[0]
                retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
                return False, retry_after

            bucket.append(now)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rules: list[RateLimitRule], enabled: bool = True) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._rules = rules
        self._store = InMemoryRateLimitStore()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._enabled:
            return await call_next(request)

        rule = self._match_rule(request.url.path, request.method)
        if rule is None:
            return await call_next(request)

        identifier = self._resolve_identifier(request)
        key = f"{rule.name}:{identifier}"
        allowed, retry_after = self._store.check_and_mark(
            key=key,
            max_requests=rule.max_requests,
            window_seconds=rule.window_seconds,
        )
        if allowed:
            return await call_next(request)

        payload = build_error_payload(
            code="RATE_LIMITED",
            message="Too many requests. Please retry later.",
            detail="Rate limit exceeded",
        )
        return JSONResponse(
            status_code=429,
            content=payload,
            headers={"Retry-After": str(retry_after)},
        )

    def _match_rule(self, path: str, method: str) -> RateLimitRule | None:
        method_normalized = method.upper()
        for rule in self._rules:
            if method_normalized not in rule.methods:
                continue
            if any(path.startswith(prefix) for prefix in rule.path_prefixes):
                return rule
        return None

    @staticmethod
    def _resolve_identifier(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ip = forwarded_for.split(",", maxsplit=1)[0].strip()
        elif request.client is not None and request.client.host:
            ip = request.client.host
        else:
            ip = "unknown"

        auth_header = request.headers.get("authorization")
        if not auth_header:
            return ip

        token_hash = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()[:16]
        return f"{ip}:{token_hash}"


def build_default_rate_limit_rules(settings: Settings) -> list[RateLimitRule]:
    api_prefix = settings.api_v1_prefix
    return [
        RateLimitRule(
            name="auth",
            path_prefixes=(f"{api_prefix}/auth",),
            methods=("POST",),
            max_requests=settings.auth_rate_limit_requests,
            window_seconds=settings.auth_rate_limit_window_seconds,
        ),
        RateLimitRule(
            name="sensitive",
            path_prefixes=(
                f"{api_prefix}/reports",
                f"{api_prefix}/messages",
                f"{api_prefix}/promotions/purchase",
                f"{api_prefix}/admin",
            ),
            methods=("POST", "PUT", "PATCH", "DELETE"),
            max_requests=settings.sensitive_rate_limit_requests,
            window_seconds=settings.sensitive_rate_limit_window_seconds,
        ),
    ]
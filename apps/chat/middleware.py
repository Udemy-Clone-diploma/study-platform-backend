from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.users.authentication import CustomJWTAuthentication


@database_sync_to_async
def _get_user_for_token(raw_token: str):
    try:
        auth = CustomJWTAuthentication()
        validated_token = auth.get_validated_token(raw_token)
        return auth.get_user(validated_token)
    except (InvalidToken, TokenError, Exception):
        return AnonymousUser()


def _token_from_scope(scope) -> str | None:
    headers = dict(scope.get("headers") or [])

    authorization = headers.get(b"authorization", b"").decode("latin1")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()

    cookie_header = headers.get(b"cookie", b"").decode("latin1")
    if not cookie_header:
        return None

    cookies = SimpleCookie()
    cookies.load(cookie_header)
    morsel = cookies.get("access_token")
    return morsel.value if morsel else None


class JWTAuthMiddleware:
    """Authenticate Channels scopes with the same JWT checks used by DRF."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        token = _token_from_scope(scope)
        scope["user"] = await _get_user_for_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)


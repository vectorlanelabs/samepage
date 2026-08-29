"""SSO provider interface (M5a, plan §4): Google OAuth (OIDC) via Authlib.

Modularity seam: providers are registered in ``PROVIDERS`` keyed by the URL
segment they live under (``/auth/{name}``). Adding Apple later is a new
class plus one registry entry — the routes, schema, and session handling are
provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass

from authlib.integrations.starlette_client import OAuth

from app.settings import settings

GOOGLE_OIDC_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"


def _claim_is_true(value) -> bool:
    """Fail-closed truthiness for an OIDC boolean claim. Google sends a JSON
    bool, but some providers send the string "true"/"false" — and
    ``bool("false")`` is True, so coerce explicitly rather than trusting
    Python truthiness."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return value is True


@dataclass
class Identity:
    """Verified external identity returned by a provider's callback."""

    subject: str
    email: str
    email_verified: bool
    display_name: str | None


class GoogleProvider:
    """Google OIDC provider built on Authlib's Starlette OAuth client.

    Not configured (empty client id/secret) until the deployment env has
    ``SP_GOOGLE_CLIENT_ID`` / ``SP_GOOGLE_CLIENT_SECRET`` — the routes check
    ``configured`` and degrade the login page instead of crashing.
    """

    def __init__(self) -> None:
        oauth = OAuth()
        oauth.register(
            "google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=GOOGLE_OIDC_METADATA_URL,
            client_kwargs={"scope": "openid email profile"},
        )
        self._client = oauth.google

    @property
    def configured(self) -> bool:
        return bool(settings.google_client_id and settings.google_client_secret)

    async def authorize_redirect(self, request, redirect_uri):
        """Redirect the browser to Google's consent screen (Authlib)."""
        return await self._client.authorize_redirect(request, redirect_uri)

    async def get_identity(self, request) -> Identity:
        """Exchange the callback code for an OIDC token and read its claims.

        Authlib parses the id_token into ``token["userinfo"]``; the ``sub``
        claim is the stable subject, ``email`` is the verified-at-Google
        email (the human-facing account key), ``email_verified`` gates
        sign-in, and ``name`` is the display-name hint.
        """
        token = await self._client.authorize_access_token(request)
        claims = token["userinfo"]
        return Identity(
            subject=claims["sub"],
            email=claims["email"].lower(),
            email_verified=_claim_is_true(claims.get("email_verified")),
            display_name=claims.get("name"),
        )


PROVIDERS: dict[str, GoogleProvider] = {"google": GoogleProvider()}

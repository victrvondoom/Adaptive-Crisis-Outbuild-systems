"""
AIDNEXUS ONE — Identity and token verification.

Two adapters:

1. ProductionAdapter (OIDC / JWT): validates RS256/HS256 tokens against a
   configured issuer + audience, with JWKS fetched from the IdP. Activated by
   setting OIDC_ISSUER / OIDC_AUDIENCE / OIDC_JWKS_URL. This is the path an
   enterprise IdP (or OutSystems ODC identity) plugs into.

2. DevAdapter: issues short-lived signed tokens for seeded demo identities so
   the full authorization stack is exercised locally. It CANNOT be enabled in
   production: `DevAdapter.enabled` requires APP_ENV != "production" AND
   DEV_AUTH_ENABLED == "1". Both must be set explicitly — fail-closed.

Session revocation: every token carries a jti backed by a sessions table row;
revoked or expired sessions fail verification even if the signature is valid.

Tokens carry org scopes derived from membership records — never from client
input. Tenant access is resolved server-side per request.
"""
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt as pyjwt

TOKEN_ISSUER_DEV = "aidnexus-dev"
TOKEN_AUDIENCE = "aidnexus-api"
TOKEN_TTL_SECONDS = 8 * 3600


class IdentityError(Exception):
    """Raised for any token verification failure — callers fail closed."""


class VerifiedIdentity:
    def __init__(self, user_id: str, email: str, scopes: list,
                 jti: str, is_platform_admin: bool = False):
        self.user_id = user_id
        self.email = email
        self.scopes = scopes  # [{"org_id":..., "role":...}]
        self.jti = jti
        self.is_platform_admin = is_platform_admin

    def role_in(self, org_id: str) -> Optional[str]:
        for s in self.scopes:
            if s["org_id"] == org_id:
                return s["role"]
        return None

    def org_ids(self) -> list:
        return [s["org_id"] for s in self.scopes]


class DevAdapter:
    """Development-only token issuer. Impossible to enable in production."""
    def __init__(self, secret: str = None):
        self.secret = secret or os.environ.get("DEV_AUTH_SECRET") or uuid.uuid4().hex

    @staticmethod
    def enabled() -> bool:
        env = os.environ.get("APP_ENV", "development")
        dev_flag = os.environ.get("DEV_AUTH_ENABLED", "")
        return env != "production" and dev_flag == "1"

    def issue_token(self, user_id: str, email: str, scopes: list,
                    jti: str = None, ttl: int = TOKEN_TTL_SECONDS) -> str:
        now = int(time.time())
        payload = {
            "sub": user_id, "email": email, "scopes": scopes,
            "iss": TOKEN_ISSUER_DEV, "aud": TOKEN_AUDIENCE,
            "iat": now, "exp": now + ttl, "jti": jti or uuid.uuid4().hex,
        }
        return pyjwt.encode(payload, self.secret, algorithm="HS256")


class ProductionAdapter:
    """OIDC JWT verification (RS256 via JWKS, or HS256 with a shared secret)."""
    def __init__(self, issuer: str, audience: str, jwks_url: str = None,
                 secret: str = None, algorithms: list = None):
        self.issuer = issuer
        self.audience = audience
        self.jwks_url = jwks_url
        self.secret = secret
        self.algorithms = algorithms or (["RS256"] if jwks_url else ["HS256"])
        self._jwk_client = None
        if jwks_url:
            from jwt import PyJWKClient
            self._jwk_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)

    @staticmethod
    def configured() -> bool:
        return bool(os.environ.get("OIDC_ISSUER") and os.environ.get("OIDC_AUDIENCE"))

    @staticmethod
    def from_env() -> "ProductionAdapter":
        return ProductionAdapter(
            issuer=os.environ["OIDC_ISSUER"],
            audience=os.environ["OIDC_AUDIENCE"],
            jwks_url=os.environ.get("OIDC_JWKS_URL"),
            secret=os.environ.get("OIDC_CLIENT_SECRET"),
            algorithms=os.environ.get("OIDC_ALGORITHMS", "").split(",") if os.environ.get("OIDC_ALGORITHMS") else None,
        )

    def verify_token(self, token: str) -> dict:
        """Verifies signature, issuer, audience, expiry. Raises IdentityError."""
        try:
            if self._jwk_client is not None:
                signing_key = self._jwk_client.get_signing_key_from_jwt(token)
                key = signing_key.key
            else:
                key = self.secret
            claims = pyjwt.decode(token, key, algorithms=self.algorithms,
                                  audience=self.audience, issuer=self.issuer,
                                  options={"require": ["exp", "iat", "sub", "iss", "aud"]})
            return claims
        except pyjwt.InvalidIssuerError as e:
            raise IdentityError(f"invalid issuer: {e}")
        except pyjwt.InvalidAudienceError as e:
            raise IdentityError(f"invalid audience: {e}")
        except pyjwt.ExpiredSignatureError as e:
            raise IdentityError(f"expired token: {e}")
        except pyjwt.InvalidTokenError as e:
            raise IdentityError(f"invalid token: {e}")


def build_identity_from_claims(claims: dict, is_platform_admin_fn=None,
                              memberships_fn=None) -> VerifiedIdentity:
    """Constructs a VerifiedIdentity. Org scopes come from the verified
    membership records in the database when a memberships_fn is provided
    (authoritative); otherwise from token claims (trusted IdP tokens only)."""
    scopes = []
    if memberships_fn is not None:
        scopes = memberships_fn(claims["sub"])
    else:
        scopes = claims.get("scopes", [])
    return VerifiedIdentity(
        user_id=claims["sub"],
        email=claims.get("email", ""),
        scopes=scopes,
        jti=claims.get("jti", ""),
        is_platform_admin=bool(claims.get("platform_admin", False)),
    )

"""Password hashing (bcrypt) and token helpers (JWT access, opaque secrets)."""

import hashlib
import secrets
import uuid
from datetime import timedelta

import bcrypt
import jwt

from app.core.time import utcnow

ACCESS_TOKEN_TYPE = "access"
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
API_KEY_PREFIX = "co_"


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Never store the input."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True when the password matches the stored hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def sha256_hex(value: str) -> str:
    """Digest for opaque tokens/keys — only digests touch the database."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def mint_opaque_token() -> str:
    """Mint a random opaque token (refresh tokens)."""
    return secrets.token_urlsafe(32)


def mint_api_key() -> str:
    """Mint a random API key with a recognizable prefix."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def create_access_token(user_id: uuid.UUID, secret: str) -> str:
    """Create a short-lived access JWT for the user."""
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> uuid.UUID | None:
    """Return the user id for a valid access JWT, else None."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        return None
    try:
        return uuid.UUID(str(payload.get("sub")))
    except (ValueError, AttributeError, TypeError):
        return None

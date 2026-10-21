"""Password hashing and JWT security helpers."""

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID
from jose import JWTError, jwt
from passlib.context import CryptContext
from sawakli.core.config import settings
import bcrypt
bcrypt.__about__ = type('About', (object,), {'__version__': bcrypt.__version__})

pwd_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__rounds=12,
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return cast(str, pwd_context.hash(password))


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    return cast(bool, pwd_context.verify(password, hashed_password))


def create_access_token(user_id: UUID, organization_id: UUID) -> str:
    """Create a JWT containing the user and organization IDs."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)

    payload = {
        "sub": str(user_id),
        "org_id": str(organization_id),
        "exp": expire,
    }

    return cast(str, jwt.encode(payload, settings.jwt_secret, algorithm="HS256"))


def decode_access_token(token: str) -> tuple[UUID, UUID]:
    """Decode a JWT and return its user and organization IDs."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )

        user_id = UUID(payload["sub"])
        organization_id = UUID(payload["org_id"])

        return user_id, organization_id

    except (JWTError, KeyError, ValueError) as exc:
        raise ValueError("Invalid or expired token") from exc

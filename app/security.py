from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import get_settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(value: str) -> str:
    return pwd.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    return pwd.verify(value, hashed)


def create_token(user_id: str, organization_id: str, role: str, token_type: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": user_id, "org": organization_id, "role": role, "type": token_type, "iat": now, "exp": now + timedelta(minutes=minutes)},
        settings.secret_key,
        algorithm="HS256",
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("Incorrect token type")
    return payload

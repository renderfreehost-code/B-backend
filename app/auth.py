import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.hash import bcrypt, bcrypt_sha256
from fastapi import Header, HTTPException
from .database import get_conn

SECRET = os.getenv("JWT_SECRET", "change-this-secret")
ALGO = "HS256"

def hash_password(password: str) -> str:
    """Hash passwords safely for bcrypt.

    bcrypt has a 72-byte password limit. bcrypt_sha256 pre-hashes first,
    so long ADMIN_PASSWORD values will not crash Render startup.
    """
    if password is None:
        raise ValueError("Password is required")
    return bcrypt_sha256.hash(str(password))

def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    try:
        if str(hashed).startswith("$bcrypt-sha256$"):
            return bcrypt_sha256.verify(str(password), hashed)
        # Backward compatibility for older bcrypt hashes created before this fix.
        return bcrypt.verify(str(password)[:72], hashed)
    except Exception:
        return False

def create_token(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "is_admin": bool(user["is_admin"]),
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGO])
        user_id = int(data["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,email,balance,is_admin,created_at FROM users WHERE id=%s", (user_id,))
            user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def admin_user(user = None):
    if not user or not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin only")
    return user

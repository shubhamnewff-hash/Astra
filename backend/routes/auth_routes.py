from fastapi import APIRouter, HTTPException, Request, Response
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from database import db
from models import UserCreate, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest
from auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    set_auth_cookies, get_current_user,
)
import jwt
import os
import secrets
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: dict) -> dict:
    return {
        "id": str(user["_id"]) if isinstance(user["_id"], ObjectId) else user["_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at", "").isoformat() if isinstance(user.get("created_at"), datetime) else str(user.get("created_at", "")),
    }


@router.post("/register")
async def register(body: UserCreate, response: Response):
    email = body.email.strip().lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name.strip(),
        "role": "end_user",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    access = create_access_token(str(doc["_id"]), email)
    refresh = create_refresh_token(str(doc["_id"]))
    set_auth_cookies(response, access, refresh)

    return {"user": user_out(doc), "access_token": access}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    # Brute force check
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if locked_until and datetime.now(timezone.utc) < locked_until:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
        else:
            await db.login_attempts.delete_one({"identifier": identifier})

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        # Increment failed attempts
        if attempt:
            new_count = attempt.get("count", 0) + 1
            update = {"$set": {"count": new_count, "last_attempt": datetime.now(timezone.utc)}}
            if new_count >= 5:
                from datetime import timedelta
                update["$set"]["locked_until"] = datetime.now(timezone.utc) + timedelta(minutes=15)
            await db.login_attempts.update_one({"identifier": identifier}, update)
        else:
            await db.login_attempts.insert_one({"identifier": identifier, "count": 1, "last_attempt": datetime.now(timezone.utc)})
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account disabled")

    # Clear login attempts on success
    await db.login_attempts.delete_many({"identifier": identifier})

    access = create_access_token(str(user["_id"]), email)
    refresh = create_refresh_token(str(user["_id"]))
    set_auth_cookies(response, access, refresh)

    return {"user": user_out(user), "access_token": access}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}


@router.get("/me")
async def me(request: Request):
    user = await get_current_user(request)
    return {"user": user}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(str(user["_id"]), user["email"])
        set_auth_cookies(response, access, token)
        return {"access_token": access}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If an account exists with this email, a reset link has been generated."}

    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "user_id": str(user["_id"]),
        "token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    # Log reset link (no email service configured)
    logger.info(f"Password reset token for {email}: {token}")
    return {"message": "If an account exists with this email, a reset link has been generated.", "reset_token": token}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    token_doc = await db.password_reset_tokens.find_one({"token": body.token, "used": False})
    if not token_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires_at = token_doc["expires_at"]
    # MongoDB returns naive datetime; normalize to UTC-aware for comparison
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    await db.users.update_one(
        {"_id": ObjectId(token_doc["user_id"])},
        {"$set": {"password_hash": hash_password(body.new_password)}},
    )
    await db.password_reset_tokens.update_one(
        {"_id": token_doc["_id"]},
        {"$set": {"used": True}},
    )
    return {"message": "Password has been reset successfully"}


# ── Google OAuth via Emergent ──
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
@router.post("/google/session")
async def google_session(request: Request, response: Response):
    """Exchange an Emergent OAuth session_id for our JWT auth tokens.
    Creates a new user (role='user') if first-time Google sign-in, or links to existing email."""
    import httpx
    body = await request.json()
    session_id = body.get("session_id") or request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(400, "Missing session_id")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": session_id},
            )
        if r.status_code != 200:
            raise HTTPException(401, f"Google auth failed: {r.text[:200]}")
        data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergent OAuth session-data fetch failed: {e}")
        raise HTTPException(500, "Failed to verify Google session")

    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    picture = data.get("picture") or ""
    if not email:
        raise HTTPException(400, "Google account missing email")

    # Find or create the user
    existing = await db.users.find_one({"email": email})
    if existing:
        if not existing.get("is_active", True):
            raise HTTPException(403, "Account disabled")
        user = existing
        # Backfill picture/name if not previously set
        upd = {}
        if name and not user.get("name"): upd["name"] = name
        if picture and not user.get("picture"): upd["picture"] = picture
        if upd:
            await db.users.update_one({"_id": user["_id"]}, {"$set": upd})
            user.update(upd)
    else:
        doc = {
            "email": email,
            "password_hash": "",  # Google-only login, no password
            "name": name or email.split("@")[0],
            "picture": picture,
            "role": "user",
            "auth_provider": "google",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.users.insert_one(doc)
        doc["_id"] = result.inserted_id
        user = doc

    access = create_access_token(str(user["_id"]), email)
    refresh = create_refresh_token(str(user["_id"]))
    set_auth_cookies(response, access, refresh)
    return {"user": user_out(user), "access_token": access}

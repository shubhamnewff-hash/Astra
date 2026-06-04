from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI
from database import db, client
from auth import hash_password, verify_password
from routes.auth_routes import router as auth_router
from routes.knowledge_routes import router as knowledge_router
from routes.chat_routes import router as chat_router
from routes.admin_routes import router as admin_router
from datetime import datetime, timezone
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Astra - AI Knowledge Assistant")

# CORS - Dynamic origin matching for preview domains
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import re

ALLOWED_ORIGIN_PATTERNS = [
    re.compile(r"^https://.*\.preview\.emergentagent\.com$"),
    re.compile(r"^http://localhost:\d+$"),
]

cors_origins_env = os.environ.get('CORS_ORIGINS', '*')
if cors_origins_env != '*':
    static_origins = [o.strip() for o in cors_origins_env.split(',') if o.strip()]
else:
    static_origins = []


def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in static_origins:
        return True
    return any(p.match(origin) for p in ALLOWED_ORIGIN_PATTERNS)


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        origin = request.headers.get("origin", "")
        if request.method == "OPTIONS":
            if is_origin_allowed(origin):
                return StarletteResponse(
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true",
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
                        "Access-Control-Max-Age": "600",
                    },
                )
            return StarletteResponse(status_code=403)
        response = await call_next(request)
        if is_origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response


app.add_middleware(DynamicCORSMiddleware)

# Include routers
app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/api")
async def root():
    return {"message": "Astra API is running"}


@app.on_event("startup")
async def startup():
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.conversations.create_index([("user_id", 1), ("updated_at", -1)])
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])
    await db.feedback.create_index([("message_id", 1), ("user_id", 1)])
    await db.knowledge_items.create_index([("module_id", 1)])
    await db.knowledge_items.create_index([("topic_id", 1)])
    await db.tickets.create_index([("user_id", 1)])
    await db.unanswered_questions.create_index([("status", 1), ("asked_count", -1)])
    await db.unanswered_questions.create_index("normalized")
    await db.password_reset_tokens.create_index("token")

    # Text indexes for optimized search (50K+ items)
    try:
        await db.knowledge_items.create_index(
            [("title", "text"), ("question", "text"), ("keywords", "text"), ("explanation", "text")],
            weights={"title": 10, "question": 10, "keywords": 8, "explanation": 3},
            name="knowledge_text_search",
        )
    except Exception:
        pass  # Index already exists
    try:
        await db.trained_answers.create_index(
            [("question_pattern", "text"), ("keywords", "text")],
            weights={"question_pattern": 10, "keywords": 5},
            name="trained_answers_text_search",
        )
    except Exception:
        pass

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@biziverse.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "Admin@123")

    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Super Admin",
            "role": "super_admin",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        })
        logger.info(f"Admin user seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}},
        )
        logger.info("Admin password updated")

    # Seed default AI config if not exists
    ai_config = await db.ai_config.find_one({})
    if not ai_config:
        await db.ai_config.insert_one({
            "provider": "openai",
            "model": "gpt-5.2",
            "api_key": "",
            "system_prompt": "",
            "fallback_message": "I couldn't find relevant information in our knowledge base for your question.",
            "fallback_button_text": "Raise Support Ticket",
            "fallback_button_link": "",
            "show_raise_ticket": True,
            "enable_suggestions": True,
            "max_suggestions": 3,
            "confidence_threshold": 1.5,
            "suggestion_message": "I found some related topics in our knowledge base. Did you mean one of these?",
            "response_mode": "natural",
            "suggested_questions": [],
            "random_suggestions": True,
            "created_at": datetime.now(timezone.utc),
        })
        logger.info("Default AI config seeded")
    else:
        # Ensure new fields exist in existing config
        update_fields = {}
        for field, default in {
            "fallback_message": "Answer Not Found!",
            "fallback_button_text": "Raise Support Ticket",
            "show_raise_ticket": True,
            "enable_suggestions": True,
            "max_suggestions": 3,
            "confidence_threshold": 1.5,
            "suggestion_message": "I found some related topics in our knowledge base. Did you mean one of these?",
            "response_mode": "natural",
            "suggested_questions": [],
            "random_suggestions": True,
        }.items():
            if field not in ai_config:
                update_fields[field] = default
        if update_fields:
            await db.ai_config.update_one({"_id": ai_config["_id"]}, {"$set": update_fields})

    # Write test credentials
    creds_dir = Path("/app/memory")
    creds_dir.mkdir(exist_ok=True)
    (creds_dir / "test_credentials.md").write_text(
        f"# Test Credentials\n\n"
        f"## Admin Account\n"
        f"- Email: {admin_email}\n"
        f"- Password: {admin_password}\n"
        f"- Role: super_admin\n\n"
        f"## Auth Endpoints\n"
        f"- POST /api/auth/login\n"
        f"- POST /api/auth/register\n"
        f"- POST /api/auth/logout\n"
        f"- GET /api/auth/me\n"
        f"- POST /api/auth/refresh\n"
    )
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    client.close()

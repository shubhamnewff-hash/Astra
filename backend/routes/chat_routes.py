from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from bson import ObjectId
from database import db
from auth import get_current_user
from models import MessageCreate, FeedbackCreate, TicketCreate, ConversationCreate
import json
import os
import re
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


def serialize(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


STOP_WORDS = frozenset({
    "the", "how", "what", "when", "where", "which", "does", "can", "will",
    "are", "was", "is", "it", "to", "in", "of", "a", "an", "do", "i", "my",
    "me", "for", "and", "but", "not", "you", "all", "this", "that", "with",
    "from", "have", "has", "had", "been", "being", "or", "at", "by", "on",
    "if", "so", "about", "up", "out", "no", "just", "also", "than",
})


def normalize_for_match(text: str) -> str:
    """Aggressive normalization for verbatim suggestion-click matching."""
    if not text:
        return ""
    # Lowercase, strip punctuation, collapse whitespace
    s = re.sub(r"[^\w\s]", " ", text.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_content_words(text: str) -> set:
    """Extract meaningful content words, removing stop words and punctuation."""
    normalized = normalize_for_match(text)
    return set(w for w in normalized.split() if w not in STOP_WORDS and len(w) > 1)


async def find_exact_kb_match(query: str):
    """If the user query EXACTLY matches a KB item's question or title (after normalization),
    return that KB item — this is the direct suggestion-click path that bypasses LLM."""
    norm_query = normalize_for_match(query)
    if not norm_query or len(norm_query) < 6:
        return None
    items = await db.knowledge_items.find().to_list(2000)
    for item in items:
        for field in ("question", "title"):
            val = item.get(field) or ""
            if val and normalize_for_match(val) == norm_query:
                return item
    return None


async def search_trained_answers(query: str):
    """ULTRA-STRICT trained answer matching. Only exact or near-exact matches.
    The query must be asking the SAME question as the pattern."""
    normalized = query.strip().lower()
    all_trained = await db.trained_answers.find().to_list(500)

    for ta in all_trained:
        pattern = ta.get("question_pattern", "").lower().strip()

        # 1. Exact match
        if normalized == pattern:
            return ta, 100

        # 2. Very close match: remove stop words and compare
        pattern_words = extract_content_words(pattern)
        query_words = extract_content_words(normalized)

        if not pattern_words or not query_words:
            continue

        # BOTH directions must match:
        # - Almost all pattern words in query (pattern coverage)
        # - Almost all query words in pattern (query coverage = specificity)
        overlap = pattern_words & query_words
        pattern_coverage = len(overlap) / len(pattern_words)
        query_coverage = len(overlap) / len(query_words)

        # STRICT: Require BOTH 80%+ pattern coverage AND 50%+ query coverage
        # This prevents "How to enter Quick Sales Order in Biziverse?"
        # from matching "What is Biziverse?" (query_coverage would be 1/6 = 16%)
        if pattern_coverage >= 0.8 and query_coverage >= 0.5:
            score = (pattern_coverage * 50) + (query_coverage * 50)
            if score >= 70:
                return ta, score

    return None, 0


async def search_general_questions(query: str):
    """Search admin-configured general question responses (for non-KB queries like greetings)."""
    normalized = query.strip().lower()
    general_qs = await db.general_questions.find({"active": True}).to_list(100)

    for gq in general_qs:
        triggers = gq.get("triggers", [])
        for trigger in triggers:
            t = trigger.strip().lower()
            if t and (t in normalized or normalized in t):
                return gq
        # Also check the question text itself
        q_text = gq.get("question", "").lower().strip()
        if q_text and (q_text in normalized or normalized in q_text):
            return gq

    return None


async def search_knowledge_base(query: str):
    """Search KB with scores."""
    try:
        results = await db.knowledge_items.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(5).to_list(5)
        if results:
            max_score = max(r.get("score", 0) for r in results)
            return results, max_score
    except Exception:
        pass

    # Fallback regex search
    words = list(extract_content_words(query))[:5]
    if not words:
        return [], 0
    conditions = []
    for word in words:
        escaped = re.escape(word)
        conditions.append({"$or": [
            {"keywords": {"$regex": escaped, "$options": "i"}},
            {"title": {"$regex": escaped, "$options": "i"}},
            {"question": {"$regex": escaped, "$options": "i"}},
        ]})
    items = await db.knowledge_items.find({"$or": conditions}).limit(5).to_list(5)
    for item in items:
        score = 0
        for w in words:
            wl = w.lower()
            if any(wl in k.lower() for k in item.get("keywords", [])):
                score += 2
            if wl in item.get("title", "").lower():
                score += 1.5
            if wl in item.get("question", "").lower():
                score += 1.5
        item["score"] = score
    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    max_score = items[0].get("score", 0) if items else 0
    return items, max_score


def get_kb_suggestions(items, max_count=3, module_filter=None):
    """Extract actual KB questions as suggestions. NEVER fabricate."""
    suggestions = []
    for item in items:
        # Apply module filter if set
        if module_filter and item.get("module_id") and item["module_id"] not in module_filter:
            continue
        q = item.get("question") or item.get("title", "")
        q = q.strip()
        if q and q not in suggestions:
            suggestions.append(q)
        if len(suggestions) >= max_count:
            break
    return suggestions


def build_knowledge_context(items):
    """Build context for AI — preserve markdown/bold."""
    parts = []
    for item in items:
        lines = [f"**{item.get('title', '')}**"]
        if item.get("question"):
            lines.append(f"Question: {item['question']}")
        if item.get("explanation"):
            lines.append(item["explanation"])
        if item.get("steps"):
            lines.append("Steps:\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(item["steps"])))
        if item.get("suggestions"):
            lines.append("Tips: " + " | ".join(item["suggestions"]))
        parts.append("\n".join(lines))
    return "KNOWLEDGE BASE CONTEXT:\n\n" + "\n---\n".join(parts)


SYSTEM_PROMPT = """You are Astra, the AI Knowledge Assistant for Biziverse.

ABSOLUTE RULES — ZERO EXCEPTIONS:

1. Answer ONLY using the KNOWLEDGE BASE CONTEXT below. Nothing else.
2. Do NOT add ANY information not in the context. Zero tolerance.
3. Do NOT speculate, guess, infer, or assume anything.
4. Do NOT use hedging language: "typically", "usually", "I believe", "generally".
5. Present ONLY what the context contains — clearly, concisely, accurately.
6. If the context has steps, present them as numbered steps.
7. PRESERVE all **bold** text and markdown formatting from the context.
8. If the context does NOT contain a clear answer, respond with EXACTLY: {{FALLBACK}}
9. Do NOT partially answer. Full answer from context OR {{FALLBACK}}.
10. NEVER fabricate steps, features, or workflows not in the context."""


def build_system_prompt(context: str, custom_prompt: str = "", fallback_message: str = "") -> str:
    prompt = SYSTEM_PROMPT.replace("{{FALLBACK}}", fallback_message)
    if custom_prompt:
        prompt = custom_prompt + "\n\n" + prompt
    return prompt + "\n\n" + context


async def track_unanswered(query: str, user_id: str, conv_id: str, source: str = "fallback"):
    """Track a query that Astra couldn't answer directly.
    source: 'fallback' (no KB match), 'suggestion' (ambiguous, showed suggestions), 'ai_uncertain' (LLM said don't know)."""
    normalized = query.strip().lower()
    existing = await db.unanswered_questions.find_one({"normalized": normalized, "status": "pending"})
    if existing:
        await db.unanswered_questions.update_one(
            {"_id": existing["_id"]},
            {"$inc": {"asked_count": 1},
             "$set": {"updated_at": datetime.now(timezone.utc), "conversation_id": conv_id, "last_source": source}},
        )
    else:
        await db.unanswered_questions.insert_one({
            "question": query.strip(), "normalized": normalized,
            "user_id": user_id, "conversation_id": conv_id,
            "asked_count": 1, "status": "pending", "last_source": source,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        })


async def detect_and_translate(text: str, api_key: str, provider: str = "openai", model: str = "gpt-5.2"):
    """Detect language of user text. If not English, translate to English for KB matching.
    Returns: (detected_lang_code, english_query). detected_lang_code is 'en' if English/ASCII.
    Bank-grade: on ANY failure, return ('en', original_text) — never break the pipeline.
    """
    stripped = text.strip()
    if not stripped:
        return ("en", stripped)

    # Quick ASCII heuristic — if 95%+ ASCII and short, assume English (skip LLM call)
    ascii_chars = sum(1 for c in stripped if ord(c) < 128)
    if len(stripped) < 80 and ascii_chars / max(len(stripped), 1) > 0.95:
        # Could still be romanized Hindi etc. Use LLM only if longer.
        # For very short ASCII (likely English), skip.
        pass

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"astra-lang-detect-{datetime.now(timezone.utc).timestamp()}",
            system_message=(
                "You are a language detection and translation system. "
                "Given a user query, respond in EXACTLY this JSON format (no markdown, no explanation):\n"
                '{"lang":"<ISO-639-1 code>","english":"<English translation>"}\n'
                "- lang must be the 2-letter ISO code (e.g., 'en', 'hi', 'es', 'fr', 'de', 'ar', 'zh', 'ja', 'pt', 'ru', 'it', 'bn', 'ta', 'te', 'mr', 'gu', 'pa', 'ur').\n"
                "- If query is already English, return english as-is.\n"
                "- If query is romanized (e.g., Hindi typed in English like 'kya hai'), detect the source language ('hi') and translate to proper English.\n"
                "- Respond with JSON only. No prose."
            ),
        )
        chat.with_model(provider, model)
        resp = await chat.send_message(UserMessage(text=stripped))
        raw = (resp or "").strip()
        # Extract JSON
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return ("en", stripped)
        data = json.loads(m.group(0))
        lang = (data.get("lang") or "en").lower()[:5]
        english = data.get("english") or stripped
        return (lang, english.strip())
    except Exception as e:
        logger.warning(f"Language detection failed: {e}")
        return ("en", stripped)


async def translate_text(text: str, target_lang: str, api_key: str, provider: str = "openai", model: str = "gpt-5.2") -> str:
    """Translate text to target_lang. Preserve markdown (**bold**, lists, numbered steps).
    On failure, return original text — never break the pipeline."""
    if not text or not text.strip():
        return text
    if target_lang in ("en", "", None):
        return text
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"astra-translate-{datetime.now(timezone.utc).timestamp()}",
            system_message=(
                f"You are a professional translator. Translate the user's text to language code '{target_lang}'.\n"
                "STRICT RULES:\n"
                "1. Preserve ALL markdown formatting: **bold**, *italic*, numbered lists (1., 2., 3.), bullet points, line breaks.\n"
                "2. Preserve technical terms, product names, brand names (e.g., Biziverse, GST, ERP) as-is in English.\n"
                "3. Preserve URLs and code blocks exactly.\n"
                "4. Do NOT add explanations, prefixes, or quotes around the output. Output ONLY the translated text.\n"
                "5. Keep the same line structure and spacing."
            ),
        )
        chat.with_model(provider, model)
        resp = await chat.send_message(UserMessage(text=text))
        return (resp or text).strip()
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return text


async def translate_list(items: list, target_lang: str, api_key: str, provider: str = "openai", model: str = "gpt-5.2") -> list:
    """Translate a list of short strings (e.g., suggestion questions, button labels). Batched."""
    if not items or target_lang in ("en", "", None):
        return items
    try:
        joined = "\n".join(f"{i+1}. {s}" for i, s in enumerate(items))
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"astra-translate-list-{datetime.now(timezone.utc).timestamp()}",
            system_message=(
                f"Translate each numbered line to language code '{target_lang}'. "
                "Preserve numbering (1., 2., 3.). Keep product names (Biziverse, GST) in English. "
                "Output ONLY the translated numbered list, nothing else."
            ),
        )
        chat.with_model(provider, model)
        resp = await chat.send_message(UserMessage(text=joined))
        if not resp:
            return items
        lines = [ln.strip() for ln in resp.strip().split("\n") if ln.strip()]
        translated = []
        for ln in lines:
            # Strip leading number
            cleaned = re.sub(r"^\d+\.\s*", "", ln).strip()
            if cleaned:
                translated.append(cleaned)
        if len(translated) == len(items):
            return translated
        return items
    except Exception as e:
        logger.warning(f"List translation failed: {e}")
        return items


def is_uncertain_response(text: str, fallback_message: str) -> bool:
    text_lower = text.strip().lower()
    if fallback_message.lower() in text_lower:
        return True
    phrases = [
        "i don't have", "i do not have", "i couldn't find", "i could not find",
        "not available in", "no information", "not in the context",
        "beyond the", "outside the", "not mentioned", "i'm not sure",
        "i am not sure", "cannot determine", "can't determine",
        "not enough information", "insufficient information",
        "no relevant information", "not covered in",
    ]
    return any(p in text_lower for p in phrases)


# ── Conversations ──
@router.get("/conversations")
async def list_conversations(request: Request):
    user = await get_current_user(request)
    ai_config = await db.ai_config.find_one({}) or {}
    limit = int(ai_config.get("max_user_conversations", 25) or 25)
    if limit < 1:
        limit = 25
    # Latest N visible
    docs = await db.conversations.find({"user_id": user["_id"]}).sort("updated_at", -1).to_list(limit + 100)
    visible = docs[:limit]
    # Auto-cleanup older convs beyond limit
    overflow = docs[limit:]
    if overflow:
        ids_to_delete = [d["_id"] for d in overflow]
        await db.conversations.delete_many({"_id": {"$in": ids_to_delete}})
        str_ids = [str(i) for i in ids_to_delete]
        await db.messages.delete_many({"conversation_id": {"$in": str_ids}})
        await db.feedback.delete_many({"conversation_id": {"$in": str_ids}})
    return [serialize(d) for d in visible]


@router.post("/conversations")
async def create_conversation(body: ConversationCreate, request: Request):
    user = await get_current_user(request)
    doc = {
        "user_id": user["_id"], "title": body.title,
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        "is_escalated": False, "review_status": "pending",
    }
    result = await db.conversations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize(doc)


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": user["_id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = await db.messages.find({"conversation_id": conv_id}).sort("created_at", 1).to_list(500)
    for msg in messages:
        msg["_id"] = str(msg["_id"])
        if msg["role"] == "assistant":
            feedback = await db.feedback.find_one({"message_id": str(msg["_id"]), "user_id": user["_id"]})
            if feedback:
                msg["feedback"] = {"is_helpful": feedback["is_helpful"], "comment": feedback.get("comment")}
        for k, v in msg.items():
            if isinstance(v, datetime):
                msg[k] = v.isoformat()
    return {"conversation": serialize(conv), "messages": messages}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, request: Request):
    user = await get_current_user(request)
    result = await db.conversations.delete_one({"_id": ObjectId(conv_id), "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Conversation not found")
    await db.messages.delete_many({"conversation_id": conv_id})
    await db.feedback.delete_many({"conversation_id": conv_id})
    return {"message": "Deleted"}


@router.get("/fallback-config")
async def get_fallback_config(request: Request):
    await get_current_user(request)
    ai_config = await db.ai_config.find_one({}) or {}
    return {
        "fallback_message": ai_config.get("fallback_message", "Answer Not Found!"),
        "fallback_button_text": ai_config.get("fallback_button_text", "Raise Support Ticket"),
        "fallback_button_link": ai_config.get("fallback_button_link", ""),
        "show_raise_ticket": ai_config.get("show_raise_ticket", True),
    }


@router.get("/home-suggestions")
async def get_home_suggestions(request: Request):
    await get_current_user(request)
    ai_config = await db.ai_config.find_one({}) or {}
    admin_questions = ai_config.get("suggested_questions", [])
    random_mode = ai_config.get("random_suggestions", False)

    if admin_questions and not random_mode:
        return {"questions": admin_questions, "source": "admin"}

    import random as rng
    kb_items = await db.knowledge_items.find({}, {"question": 1, "title": 1}).to_list(50)
    all_questions = [item.get("question") or item.get("title", "") for item in kb_items if (item.get("question") or item.get("title", "")).strip()]
    if not all_questions:
        return {"questions": admin_questions or [], "source": "default"}
    count = min(6, len(all_questions))
    return {"questions": rng.sample(all_questions, count), "source": "random"}


# ── MESSAGES: ZERO HALLUCINATION ENGINE ──
@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: str, body: MessageCreate, request: Request):
    user = await get_current_user(request)
    conv = await db.conversations.find_one({"_id": ObjectId(conv_id), "user_id": user["_id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")

    # Save user message (original language)
    await db.messages.insert_one({
        "conversation_id": conv_id, "role": "user",
        "content": body.content, "created_at": datetime.now(timezone.utc),
    })

    # Get config
    ai_config = await db.ai_config.find_one({}) or {}
    enable_suggestions = ai_config.get("enable_suggestions", True)
    max_suggestions = ai_config.get("max_suggestions", 3)
    fallback_message = ai_config.get("fallback_message", "Answer Not Found!")
    fallback_button_text = ai_config.get("fallback_button_text", "Raise Support Ticket")
    fallback_button_link = ai_config.get("fallback_button_link", "")
    show_raise_ticket = ai_config.get("show_raise_ticket", True)
    suggestion_message = ai_config.get("suggestion_message", "I found some related topics. Did you mean one of these?")
    suggestion_modules = ai_config.get("suggestion_modules", [])  # module IDs to filter
    multilingual_enabled = ai_config.get("multilingual", True)

    provider = ai_config.get("provider", "openai")
    model = ai_config.get("model", "gpt-5.2")
    api_key = ai_config.get("api_key") or os.environ.get("EMERGENT_LLM_KEY", "")
    custom_prompt = ai_config.get("system_prompt", "")

    # ════════════════════════════════════════════
    # MULTILINGUAL: Detect user language, translate to English for matching
    # ════════════════════════════════════════════
    user_lang = "en"
    english_query = body.content
    if multilingual_enabled and api_key:
        user_lang, english_query = await detect_and_translate(body.content, api_key, provider, model)
        logger.info(f"Language detected: {user_lang} | English: {english_query[:80]}")

    async def t(text):
        """Translate text to user_lang (no-op if English)."""
        return await translate_text(text, user_lang, api_key, provider, model) if user_lang != "en" else text

    async def tl(items):
        """Translate list to user_lang."""
        return await translate_list(items, user_lang, api_key, provider, model) if user_lang != "en" else items

    async def update_title(content):
        count = await db.messages.count_documents({"conversation_id": conv_id})
        upd = {"updated_at": datetime.now(timezone.utc)}
        if count <= 2:
            upd["title"] = content[:60] + ("..." if len(content) > 60 else "")
        await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": upd})

    def make_sse(events):
        async def gen():
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # ════════════════════════════════════════════
    # CONVERSATION CONTEXT: Load last few messages for context-aware queries
    # When the current query is short/follow-up (e.g., "how to configure it"),
    # we use prior user questions to enrich KB search.
    # ════════════════════════════════════════════
    prior_msgs = await db.messages.find({
        "conversation_id": conv_id,
        "role": "user",
    }).sort("created_at", -1).limit(6).to_list(6)
    # exclude the message we just inserted (latest one)
    prior_user_msgs = [m.get("content", "") for m in prior_msgs[1:6]]
    prior_user_msgs.reverse()  # chronological order

    # Enrich short follow-up queries with previous topic for KB search
    short_query_words = extract_content_words(english_query)
    enriched_query = english_query
    if len(short_query_words) <= 3 and prior_user_msgs:
        # Pull the most recent prior message that has more content
        for m in reversed(prior_user_msgs):
            if len(extract_content_words(m)) > len(short_query_words):
                enriched_query = f"{m} {english_query}"
                logger.info(f"Context-enriched query: '{english_query}' → '{enriched_query[:100]}'")
                break

    # ════════════════════════════════════════════
    # PRIORITY -1: EXACT KB MATCH (suggestion-click direct hit)
    # If user clicks a suggestion or types a question verbatim from KB,
    # serve the stored answer DIRECTLY — no LLM, no ambiguity check.
    # ════════════════════════════════════════════
    exact_item = await find_exact_kb_match(english_query)
    if exact_item:
        # Build the answer from explanation + steps
        lines = []
        if exact_item.get("explanation"):
            lines.append(exact_item["explanation"].strip())
        if exact_item.get("steps"):
            lines.append("")
            for i, s in enumerate(exact_item["steps"], 1):
                lines.append(f"{i}. {s}")
        if exact_item.get("suggestions"):
            lines.append("")
            lines.append("**Tips:** " + " | ".join(exact_item["suggestions"]))
        answer = "\n".join(lines).strip() or exact_item.get("title", "")
        answer_out = await t(answer)

        # Collect attached resources
        resource_refs = []
        if exact_item.get("resource_ids"):
            try:
                rdocs = await db.resources.find(
                    {"_id": {"$in": [ObjectId(rid) for rid in exact_item["resource_ids"]]}}
                ).to_list(20)
                for r in rdocs:
                    resource_refs.append({"title": r.get("title", ""), "type": r.get("resource_type", "document"), "url": r.get("url", "")})
            except Exception:
                pass

        msg_doc = {
            "conversation_id": conv_id, "role": "assistant",
            "content": answer_out, "has_knowledge": True,
            "knowledge_item_ids": [str(exact_item["_id"])],
            "resource_refs": resource_refs,
            "source": "kb_direct", "confidence": 100,
            "confidence_label": "KB Direct Match (100%)",
            "language": user_lang,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.messages.insert_one(msg_doc)
        await update_title(body.content)
        return make_sse([
            {"type": "token", "content": answer_out},
            {"type": "done", "message_id": str(result.inserted_id), "resources": resource_refs},
        ])

    # ════════════════════════════════════════════
    # PRIORITY 0: General Questions (greetings, non-KB)
    # ════════════════════════════════════════════
    general_q = await search_general_questions(english_query)
    if general_q:
        answer = general_q.get("response", "")
        buttons = general_q.get("buttons", [])
        suggestion_qs = general_q.get("suggestion_questions", [])

        # Translate to user language
        answer_out = await t(answer)
        buttons_out = buttons
        if user_lang != "en" and buttons:
            labels = [b.get("label", "") for b in buttons]
            translated_labels = await tl(labels)
            buttons_out = [{**b, "label": translated_labels[i] if i < len(translated_labels) else b.get("label", "")} for i, b in enumerate(buttons)]
        suggestion_qs_out = await tl(suggestion_qs) if suggestion_qs else suggestion_qs

        msg_doc = {
            "conversation_id": conv_id, "role": "assistant",
            "content": answer_out, "has_knowledge": True,
            "source": "general_question", "confidence": 100,
            "confidence_label": "General Question (Configured)",
            "language": user_lang, "buttons": buttons_out, "suggestions": suggestion_qs_out,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.messages.insert_one(msg_doc)
        await update_title(body.content)

        events = [{"type": "token", "content": answer_out}]
        done_data = {"type": "done", "message_id": str(result.inserted_id), "resources": []}
        if buttons_out:
            done_data["buttons"] = buttons_out
        if suggestion_qs_out:
            done_data["suggestions"] = suggestion_qs_out
        events.append(done_data)
        return make_sse(events)

    # ════════════════════════════════════════════
    # PRIORITY 1: Trained Answers (STRICT match only)
    # ════════════════════════════════════════════
    trained_answer, trained_score = await search_trained_answers(english_query)
    if trained_answer and trained_score >= 70:
        answer_text = trained_answer.get("answer", "")
        answer_out = await t(answer_text)
        msg_doc = {
            "conversation_id": conv_id, "role": "assistant",
            "content": answer_out, "has_knowledge": True,
            "source": "trained_answer", "confidence": 100,
            "confidence_label": "Trained Answer (Exact Match)",
            "language": user_lang,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.messages.insert_one(msg_doc)
        await update_title(body.content)
        return make_sse([
            {"type": "token", "content": answer_out},
            {"type": "done", "message_id": str(result.inserted_id), "resources": []},
        ])

    # ════════════════════════════════════════════
    # PRIORITY 2: Search Knowledge Base (with conversation-context enrichment)
    # ════════════════════════════════════════════
    knowledge_items, max_score = await search_knowledge_base(enriched_query)

    # NO MATCH → Fallback
    if not knowledge_items:
        await track_unanswered(body.content, user["_id"], conv_id, source="fallback")
        fb_out = await t(fallback_message)
        msg_doc = {
            "conversation_id": conv_id, "role": "assistant",
            "content": fb_out, "has_knowledge": False,
            "source": "fallback", "confidence": 0,
            "confidence_label": "No Match Found",
            "language": user_lang,
            "created_at": datetime.now(timezone.utc),
        }
        result = await db.messages.insert_one(msg_doc)
        await update_title(body.content)
        return make_sse([
            {"type": "fallback", "message": fb_out},
            {"type": "done", "message_id": str(result.inserted_id), "resources": [],
             "fallback": {"show": True, "message": fb_out, "button_text": fallback_button_text,
                          "button_link": fallback_button_link, "show_raise_ticket": show_raise_ticket}},
        ])

    # Get suggestions from KB (with module filter if configured)
    module_filter = suggestion_modules if suggestion_modules else None
    suggestions = get_kb_suggestions(knowledge_items, max_suggestions, module_filter) if enable_suggestions else []

    # ════════════════════════════════════════════
    # AMBIGUITY CHECK: short query (≤2 content words) OR multiple
    # KB items match with similar confidence → show suggestions.
    # Prevents Astra from concatenating several KB items into one
    # mega-answer for vague queries like "digital signature".
    # EXCEPTION: if the query matches the top KB item's title/question
    # verbatim (≥80% word overlap), trust it and answer directly.
    # ════════════════════════════════════════════
    query_words = extract_content_words(english_query)
    is_short_query = len(query_words) <= 2
    # How many items are within 60% of the top score? (i.e., similarly relevant)
    similar_count = sum(
        1 for it in knowledge_items if it.get("score", 0) >= max_score * 0.6
    ) if max_score > 0 else 0
    is_ambiguous = similar_count >= 2

    # Does the top KB item's title/question match the user's query closely?
    top_item = max(knowledge_items, key=lambda x: x.get("score", 0)) if knowledge_items else None
    top_text_words = extract_content_words(
        (top_item.get("question") or top_item.get("title", "")) if top_item else ""
    )
    top_query_coverage = (
        len(query_words & top_text_words) / len(query_words)
        if query_words and top_text_words else 0
    )
    is_verbatim_top_match = top_query_coverage >= 0.8 and len(query_words) >= 3

    force_suggestions = (
        (is_short_query or is_ambiguous)
        and not is_verbatim_top_match
        and enable_suggestions
        and len(suggestions) >= 2
    )

    # ════════════════════════════════════════════
    # BANK-LEVEL SAFETY: Score < 4 OR ambiguous → ALWAYS show suggestions
    # Never answer directly if there's any doubt
    # ════════════════════════════════════════════
    if max_score < 4 or force_suggestions:
        if suggestions:
            # Track as unanswered so admin can see what's confusing Astra
            await track_unanswered(body.content, user["_id"], conv_id, source="suggestion")
            suggestions_out = await tl(suggestions)
            sug_msg_out = await t(suggestion_message)
            msg_doc = {
                "conversation_id": conv_id, "role": "assistant",
                "content": sug_msg_out, "suggestions": suggestions_out,
                "has_knowledge": False, "source": "suggestion",
                "confidence": min(round(max_score / 5 * 100), 50),
                "confidence_label": f"Low Confidence ({min(round(max_score / 5 * 100), 50)}%) - Showing Suggestions",
                "language": user_lang,
                "created_at": datetime.now(timezone.utc),
            }
            result = await db.messages.insert_one(msg_doc)
            await update_title(body.content)
            return make_sse([
                {"type": "suggestions", "questions": suggestions_out, "message": sug_msg_out},
                {"type": "done", "message_id": str(result.inserted_id), "resources": [], "suggestions": suggestions_out},
            ])
        else:
            await track_unanswered(body.content, user["_id"], conv_id, source="fallback")
            fb_out = await t(fallback_message)
            msg_doc = {
                "conversation_id": conv_id, "role": "assistant",
                "content": fb_out, "has_knowledge": False,
                "source": "fallback", "confidence": 0,
                "confidence_label": "No Match Found",
                "language": user_lang,
                "created_at": datetime.now(timezone.utc),
            }
            result = await db.messages.insert_one(msg_doc)
            await update_title(body.content)
            return make_sse([
                {"type": "fallback", "message": fb_out},
                {"type": "done", "message_id": str(result.inserted_id), "resources": [],
                 "fallback": {"show": True, "message": fb_out, "button_text": fallback_button_text,
                              "button_link": fallback_button_link, "show_raise_ticket": show_raise_ticket}},
            ])

    # ════════════════════════════════════════════
    # HIGH CONFIDENCE (score >= 4): AI from KB Context
    # ════════════════════════════════════════════
    top_items = sorted(knowledge_items, key=lambda x: x.get("score", 0), reverse=True)[:3]
    knowledge_ids = [str(i["_id"]) for i in top_items]

    resource_refs = []
    for item in top_items:
        if item.get("resource_ids"):
            resources = await db.resources.find(
                {"_id": {"$in": [ObjectId(rid) for rid in item["resource_ids"]]}}
            ).to_list(20)
            for r in resources:
                ref = {"title": r.get("title", ""), "type": r.get("resource_type", "document"), "url": r.get("url", "")}
                if ref not in resource_refs:
                    resource_refs.append(ref)

    context = build_knowledge_context(top_items)
    # Conversation context — helps LLM understand follow-up queries
    convo_context = ""
    if prior_user_msgs:
        recent = prior_user_msgs[-4:]  # last 4 prior user messages
        convo_context = "\n\nRECENT USER QUESTIONS IN THIS CONVERSATION (for context only — do NOT answer these):\n" + "\n".join(f"- {m}" for m in recent)
    # Tell AI to respond in user's language while sourcing only from English KB context
    lang_instruction = ""
    if user_lang != "en":
        lang_instruction = (
            f"\n\nIMPORTANT: The user asked in language code '{user_lang}'. "
            f"Respond ONLY in language '{user_lang}'. Preserve all markdown formatting "
            "(**bold**, numbered lists). Keep product names (Biziverse, GST, ERP) in English."
        )
    system_prompt = build_system_prompt(context, custom_prompt, fallback_message) + convo_context + lang_instruction

    async def ai_generator():
        full_response = ""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
            chat = LlmChat(
                api_key=api_key,
                session_id=f"astra-{conv_id}-{datetime.now(timezone.utc).timestamp()}",
                system_message=system_prompt,
            )
            chat.with_model(provider, model)
            async for event in chat.stream_message(UserMessage(text=body.content)):
                if isinstance(event, TextDelta):
                    full_response += event.content
                    yield f"data: {json.dumps({'type': 'token', 'content': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            logger.error(f"AI Error: {e}")
            full_response = fallback_message
            yield f"data: {json.dumps({'type': 'token', 'content': full_response})}\n\n"

        # POST-PROCESSING: If AI is uncertain → override with fallback/suggestions
        if is_uncertain_response(full_response, fallback_message):
            await track_unanswered(body.content, user["_id"], conv_id, source="ai_uncertain")
            if suggestions:
                suggestions_out = await tl(suggestions)
                sug_msg_out = await t(suggestion_message)
                msg_doc = {
                    "conversation_id": conv_id, "role": "assistant",
                    "content": sug_msg_out, "suggestions": suggestions_out,
                    "has_knowledge": False, "source": "ai_uncertain",
                    "confidence": 10, "confidence_label": "AI Uncertain - Showing Suggestions",
                    "language": user_lang,
                    "created_at": datetime.now(timezone.utc),
                }
                r = await db.messages.insert_one(msg_doc)
                await update_title(body.content)
                yield f"data: {json.dumps({'type': 'override', 'content': sug_msg_out, 'suggestions': suggestions_out})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': str(r.inserted_id), 'resources': [], 'suggestions': suggestions_out})}\n\n"
            else:
                fb_out = await t(fallback_message)
                msg_doc = {
                    "conversation_id": conv_id, "role": "assistant",
                    "content": fb_out, "has_knowledge": False,
                    "source": "ai_fallback", "confidence": 0,
                    "confidence_label": "AI Could Not Answer",
                    "language": user_lang,
                    "created_at": datetime.now(timezone.utc),
                }
                r = await db.messages.insert_one(msg_doc)
                await update_title(body.content)
                yield f"data: {json.dumps({'type': 'override', 'content': fb_out})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'message_id': str(r.inserted_id), 'resources': [], 'fallback': {'show': True, 'message': fb_out, 'button_text': fallback_button_text, 'button_link': fallback_button_link, 'show_raise_ticket': show_raise_ticket}})}\n\n"
            return

        # Good AI response from KB
        kb_score = top_items[0].get("score", 0) if top_items else 0
        conf = min(round(kb_score / 8 * 100), 95)
        msg_doc = {
            "conversation_id": conv_id, "role": "assistant",
            "content": full_response, "knowledge_item_ids": knowledge_ids,
            "resource_refs": resource_refs, "has_knowledge": True,
            "source": "ai_kb", "confidence": conf,
            "confidence_label": f"AI from KB ({conf}%)",
            "language": user_lang,
            "created_at": datetime.now(timezone.utc),
        }
        r = await db.messages.insert_one(msg_doc)
        await update_title(body.content)
        yield f"data: {json.dumps({'type': 'done', 'message_id': str(r.inserted_id), 'resources': resource_refs})}\n\n"

    return StreamingResponse(ai_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Feedback ──
@router.post("/feedback")
async def submit_feedback(body: FeedbackCreate, request: Request):
    user = await get_current_user(request)
    existing = await db.feedback.find_one({"message_id": body.message_id, "user_id": user["_id"]})
    if existing:
        await db.feedback.update_one(
            {"_id": existing["_id"]},
            {"$set": {"is_helpful": body.is_helpful, "comment": body.comment, "updated_at": datetime.now(timezone.utc)}},
        )
        return {"message": "Feedback updated"}
    doc = {
        "message_id": body.message_id, "conversation_id": body.conversation_id,
        "user_id": user["_id"], "is_helpful": body.is_helpful,
        "comment": body.comment, "created_at": datetime.now(timezone.utc),
    }
    await db.feedback.insert_one(doc)
    return {"message": "Feedback submitted"}


# ── Tickets ──
@router.post("/tickets")
async def create_ticket(body: TicketCreate, request: Request):
    user = await get_current_user(request)
    doc = {
        "user_id": user["_id"], "user_email": user["email"],
        "user_name": user.get("name", ""), "question": body.question,
        "ai_response": body.ai_response, "conversation_id": body.conversation_id,
        "status": "open", "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    }
    result = await db.tickets.insert_one(doc)
    doc["_id"] = result.inserted_id
    if body.conversation_id:
        await db.conversations.update_one({"_id": ObjectId(body.conversation_id)}, {"$set": {"is_escalated": True}})
    return serialize(doc)


@router.get("/tickets")
async def list_user_tickets(request: Request):
    user = await get_current_user(request)
    docs = await db.tickets.find({"user_id": user["_id"]}).sort("created_at", -1).to_list(100)
    return [serialize(d) for d in docs]

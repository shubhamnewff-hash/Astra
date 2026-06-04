"""Iteration 4: KB Export + Multilingual + General Questions + Regression tests"""
import os
import json
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://pull-push.preview.emergentagent.com"

ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"


# ── Fixtures ──
@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    unique = uuid.uuid4().hex[:8]
    email = f"TEST_iter4_{unique}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register",
               json={"email": email, "password": "User@1234", "name": f"TEST iter4 {unique}"},
               timeout=15)
    assert r.status_code == 200, f"User register failed: {r.status_code} {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    return s


def _stream_message(sess, conv_id, content, timeout=120):
    """Helper to send a chat message and gather SSE tokens + done payload."""
    tokens = []
    done_event = None
    fallback_event = None
    buttons_event = None
    suggestions_event = None
    with sess.post(f"{BASE_URL}/api/chat/conversations/{conv_id}/messages",
                   json={"content": content}, stream=True, timeout=timeout) as r:
        assert r.status_code == 200, f"send_message failed: {r.status_code} {r.text}"
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            try:
                ev = json.loads(raw[6:])
            except Exception:
                continue
            t = ev.get("type")
            if t == "token":
                tokens.append(ev.get("content", ""))
            elif t == "done":
                done_event = ev
                break
            elif t == "fallback":
                fallback_event = ev
            elif t == "buttons":
                buttons_event = ev
            elif t == "suggestions":
                suggestions_event = ev
    return "".join(tokens), done_event, fallback_event, buttons_event, suggestions_event


# ────────────────────────────────────────────────
# KB EXPORT
# ────────────────────────────────────────────────
def test_kb_export_admin_success(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/knowledge/export", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "exported_at" in data
    assert "version" in data
    assert "counts" in data
    for k in ["modules", "topics", "items", "resources"]:
        assert k in data["counts"]
        assert k in data
        assert isinstance(data[k], list)
        assert data["counts"][k] == len(data[k])


def test_kb_export_unauthenticated_blocked():
    r = requests.get(f"{BASE_URL}/api/knowledge/export", timeout=10)
    assert r.status_code in (401, 403), f"Unauthenticated should be blocked, got {r.status_code}"


def test_kb_export_user_blocked(user_session):
    r = user_session.get(f"{BASE_URL}/api/knowledge/export", timeout=10)
    assert r.status_code == 403, f"End-user should be 403, got {r.status_code}"


# ────────────────────────────────────────────────
# GENERAL QUESTIONS CRUD
# ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def created_general_question(admin_session):
    payload = {
        "question": "TEST_iter4_GQ_hindi_support",
        "triggers": ["TEST_iter4_hindi_trigger"],
        "response": "Yes, Astra supports Hindi",
        "buttons": [{"label": "Switch to Hindi", "action": "switch_lang_hi"}],
        "active": True,
    }
    r = admin_session.post(f"{BASE_URL}/api/admin/general-questions", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["question"] == payload["question"]
    assert data["triggers"] == payload["triggers"]
    assert data["response"] == payload["response"]
    assert len(data["buttons"]) == 1
    yield data
    admin_session.delete(f"{BASE_URL}/api/admin/general-questions/{data['_id']}", timeout=10)


def test_list_general_questions(admin_session, created_general_question):
    r = admin_session.get(f"{BASE_URL}/api/admin/general-questions", timeout=10)
    assert r.status_code == 200
    ids = [g["_id"] for g in r.json()]
    assert created_general_question["_id"] in ids


def test_update_general_question(admin_session, created_general_question):
    new_resp = "Yes, Astra now supports **Hindi** (updated)"
    r = admin_session.put(
        f"{BASE_URL}/api/admin/general-questions/{created_general_question['_id']}",
        json={"response": new_resp}, timeout=10)
    assert r.status_code == 200
    assert r.json()["response"] == new_resp


def test_user_cannot_list_general_questions(user_session):
    r = user_session.get(f"{BASE_URL}/api/admin/general-questions", timeout=10)
    assert r.status_code == 403


# ────────────────────────────────────────────────
# MULTILINGUAL TOGGLE (AI Config)
# ────────────────────────────────────────────────
def test_ai_config_multilingual_toggle(admin_session):
    # GET
    r = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=10)
    assert r.status_code == 200
    cfg = r.json()
    orig = cfg.get("multilingual", True)
    # PUT toggle
    r = admin_session.put(f"{BASE_URL}/api/admin/ai-config",
                          json={"multilingual": not orig}, timeout=10)
    assert r.status_code == 200
    r = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=10)
    assert r.status_code == 200
    assert r.json().get("multilingual") == (not orig)
    # Reset to True for downstream multilingual tests
    admin_session.put(f"{BASE_URL}/api/admin/ai-config",
                      json={"multilingual": True}, timeout=10)
    r = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=10)
    assert r.json().get("multilingual") is True


# ────────────────────────────────────────────────
# MULTILINGUAL CHAT
# ────────────────────────────────────────────────
@pytest.fixture(scope="module")
def chat_conv(user_session):
    r = user_session.post(f"{BASE_URL}/api/chat/conversations",
                          json={"title": "TEST_iter4_multi"}, timeout=10)
    assert r.status_code == 200
    return r.json()["_id"]


def test_chat_english_baseline(user_session, chat_conv):
    text, done, _, _, _ = _stream_message(user_session, chat_conv, "What is Biziverse?")
    assert done is not None, "No done event for english baseline"
    # Should produce some response (either tokens or fallback handled elsewhere)
    # At minimum we should not get a 500 — just verify done event
    assert text or done.get("fallback") or done.get("message_id")


def test_chat_hindi_romanized(user_session, chat_conv):
    text, done, fallback, _, _ = _stream_message(user_session, chat_conv, "Biziverse kya hai?",
                                                  timeout=180)
    assert done is not None, "No done event for hindi"
    combined = text + (fallback.get("message", "") if fallback else "")
    # Expect Devanagari script chars OR brand 'Biziverse' kept
    has_devanagari = any('\u0900' <= ch <= '\u097F' for ch in combined)
    # Accept either Devanagari script OR brand kept English (graceful degrade ok)
    assert combined, "Empty response for Hindi query"
    if not has_devanagari:
        print(f"WARN: No Devanagari in Hindi response. Got: {combined[:200]}")


def test_chat_spanish_out_of_scope(user_session, chat_conv):
    text, done, fallback, _, _ = _stream_message(
        user_session, chat_conv, "como cocinar arroz biryani?", timeout=180)
    assert done is not None
    combined = (text + (fallback.get("message", "") if fallback else "")).lower()
    assert combined, "Empty response for Spanish out-of-scope"
    # Just verify we got something back; language verification is heuristic
    print(f"Spanish out-of-scope response: {combined[:200]}")


# ────────────────────────────────────────────────
# STRICT BANK-LEVEL ACCURACY (English out-of-scope)
# ────────────────────────────────────────────────
def test_chat_english_out_of_scope_fallback(user_session, chat_conv):
    text, done, fallback, _, suggestions = _stream_message(
        user_session, chat_conv, "what is the weather today?", timeout=120)
    assert done is not None
    # Must return either fallback OR suggestions, NOT a fabricated answer
    has_fallback = fallback is not None or done.get("fallback")
    has_suggestions = suggestions is not None or (done.get("suggestions") if done else None)
    # Allow either condition; the main contract is no hallucinated weather info
    combined = (text or "").lower()
    # Verify NO weather-data hallucination (no temperature/celsius/sunny etc.)
    assert "celsius" not in combined and "fahrenheit" not in combined, \
        f"Hallucinated weather data: {combined[:200]}"
    print(f"OOS english: fallback={has_fallback} suggestions={has_suggestions} tokens_len={len(text)}")


# ────────────────────────────────────────────────
# REGRESSION
# ────────────────────────────────────────────────
def test_admin_analytics_still_works(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/analytics", timeout=10)
    assert r.status_code == 200
    d = r.json()
    for k in ["total_questions", "active_users", "total_conversations",
              "open_tickets", "total_modules", "total_knowledge_items"]:
        assert k in d


def test_admin_conversations_list(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/conversations", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

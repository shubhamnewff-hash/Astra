"""Iteration 7 backend tests: ambiguous/short query → suggestions; specific query → KB answer."""
import os
import json
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://pull-push.preview.emergentagent.com"
ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def conv_id(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/chat/conversations", json={"title": "TEST_iter7"}, timeout=20)
    assert r.status_code in (200, 201), f"create conv failed: {r.status_code} {r.text[:200]}"
    return r.json()["_id"]


def _send_message(session, conv_id, content, timeout=90):
    """Send chat message, parse SSE events, return list of event dicts."""
    url = f"{BASE_URL}/api/chat/conversations/{conv_id}/messages"
    r = session.post(url, json={"content": content}, stream=True, timeout=timeout)
    assert r.status_code == 200, f"send msg failed: {r.status_code} {r.text[:200]}"
    events = []
    buf = ""
    for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
        if not chunk:
            continue
        buf += chunk
        while "\n\n" in buf:
            raw, buf = buf.split("\n\n", 1)
            for line in raw.splitlines():
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass
    return events


# ── BUG FIX: short / ambiguous queries should return suggestions ──
@pytest.mark.parametrize("query", ["digital signature", "biziverse", "sales order", "eway bill"])
def test_vague_query_returns_suggestions(admin_session, conv_id, query):
    events = _send_message(admin_session, conv_id, query)
    assert events, f"No SSE events for '{query}'"
    types = [e.get("type") for e in events]
    # Must contain a suggestions event (not just tokens)
    assert "suggestions" in types, f"'{query}' did not return suggestions. Got types: {types}"
    sug_ev = next(e for e in events if e.get("type") == "suggestions")
    questions = sug_ev.get("questions", [])
    assert isinstance(questions, list) and len(questions) >= 1, f"empty suggestions for '{query}'"
    assert len(questions) <= 3, f"more than 3 suggestions for '{query}': {len(questions)}"
    # Must NOT have streamed a token-based mega-answer
    token_events = [e for e in events if e.get("type") == "token"]
    assert len(token_events) == 0, f"'{query}' streamed tokens instead of suggestions: {len(token_events)} token events"
    # done event must include suggestions
    done_ev = next((e for e in events if e.get("type") == "done"), None)
    assert done_ev is not None, f"no done event for '{query}'"
    assert done_ev.get("suggestions"), f"done event missing suggestions for '{query}'"


# ── BUG FIX: specific query should return direct KB streamed answer ──
@pytest.mark.parametrize("query", [
    "What is Biziverse?",
    "How to generate e-Way Bill Directly from Biziverse?",
])
def test_specific_query_returns_direct_answer(admin_session, conv_id, query):
    events = _send_message(admin_session, conv_id, query, timeout=120)
    assert events, f"No SSE events for '{query}'"
    types = [e.get("type") for e in events]
    token_events = [e for e in events if e.get("type") == "token"]
    suggestions_events = [e for e in events if e.get("type") == "suggestions"]
    # Direct answer = streamed tokens, no 'suggestions' event
    assert len(token_events) >= 1, f"'{query}' did not stream tokens. Types: {types}"
    assert len(suggestions_events) == 0, f"'{query}' returned suggestions instead of direct answer"
    full_text = "".join(e.get("content", "") for e in token_events)
    assert len(full_text.strip()) > 20, f"'{query}' returned tiny answer: '{full_text}'"


# ── Cleanup ──
def test_cleanup(admin_session, conv_id):
    r = admin_session.delete(f"{BASE_URL}/api/chat/conversations/{conv_id}", timeout=15)
    assert r.status_code in (200, 204), f"cleanup failed: {r.status_code}"

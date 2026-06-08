"""Iteration 8 backend tests:
   (1) DIRECT-SERVE: verbatim KB question → kb_direct stored answer, no LLM, no suggestions.
   (2) Ambiguity still works for vague queries (single-word or multi-match).
   (3) Context enrichment: short follow-up uses prior message for KB search.
   (4) Gap tracking: source='suggestion' / 'fallback' / 'ai_uncertain' persisted with conversation_id.
"""
import os
import json
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pull-push.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"

# KB items currently seeded (verbatim)
KB_VERBATIM_QUESTION = "How to Add and Configure GST Ledgers for a Branch ?"  # exact title in KB
KB_TYPO_QUESTION = "How to Add Extra Charges bbefore GST ?"  # typo intentionally preserved in seed


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def conv_id(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/chat/conversations",
                           json={"title": "TEST_iter8"}, timeout=20)
    assert r.status_code in (200, 201), f"conv create failed: {r.status_code}"
    return r.json()["_id"]


def _send(session, conv_id, content, timeout=90):
    url = f"{BASE_URL}/api/chat/conversations/{conv_id}/messages"
    r = session.post(url, json={"content": content}, stream=True, timeout=timeout)
    assert r.status_code == 200, f"send failed: {r.status_code} {r.text[:200]}"
    events, buf = [], ""
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


def _last_assistant_msg(session, conv_id):
    r = session.get(f"{BASE_URL}/api/chat/conversations/{conv_id}", timeout=15)
    assert r.status_code == 200, f"GET conv failed: {r.status_code} {r.text[:200]}"
    msgs = r.json().get("messages", [])
    assistants = [m for m in msgs if m.get("role") == "assistant"]
    return assistants[-1] if assistants else None


# ── (1) DIRECT-SERVE: verbatim KB question returns stored answer ──
def test_direct_serve_verbatim_kb_question(admin_session, conv_id):
    events = _send(admin_session, conv_id, KB_VERBATIM_QUESTION, timeout=60)
    types = [e.get("type") for e in events]
    assert "suggestions" not in types, f"verbatim KB question should NOT return suggestions. types={types}"
    token_evs = [e for e in events if e.get("type") == "token"]
    assert len(token_evs) >= 1, f"verbatim KB question should stream token event(s). types={types}"
    full = "".join(e.get("content", "") for e in token_evs)
    # Stored explanation usually has steps and/or markdown bold
    assert len(full.strip()) > 40, f"direct-served answer too short: {full!r}"
    # Verify DB persistence: source=kb_direct, confidence=100
    msg = _last_assistant_msg(admin_session, conv_id)
    assert msg is not None
    assert msg.get("source") == "kb_direct", f"expected source=kb_direct, got {msg.get('source')}"
    assert msg.get("confidence") == 100, f"expected confidence=100, got {msg.get('confidence')}"


# ── (1b) DIRECT-SERVE another verbatim KB question (Non-GST Sales Invoice) — ensures path works for multiple items ──
def test_direct_serve_second_verbatim(admin_session, conv_id):
    events = _send(admin_session, conv_id, "How to Create a Non-GST Sales Invoice ?", timeout=60)
    token_evs = [e for e in events if e.get("type") == "token"]
    sug_evs = [e for e in events if e.get("type") == "suggestions"]
    assert len(sug_evs) == 0, "Verbatim KB question must NOT return suggestions"
    assert len(token_evs) >= 1, "Verbatim KB question must stream tokens"
    msg = _last_assistant_msg(admin_session, conv_id)
    assert msg and msg.get("source") == "kb_direct", f"expected kb_direct, got source={msg.get('source') if msg else None}"
    assert msg.get("confidence") == 100


# ── (2) AMBIGUITY still works for vague queries ──
# Use queries that won't accidentally hit trained_answers/general_questions
@pytest.mark.parametrize("vague", ["extra charges", "sales invoice"])
def test_vague_query_returns_suggestions(admin_session, conv_id, vague):
    events = _send(admin_session, conv_id, vague, timeout=60)
    types = [e.get("type") for e in events]
    assert "suggestions" in types, f"'{vague}' should return suggestions. types={types}"
    sug_ev = next(e for e in events if e.get("type") == "suggestions")
    qs = sug_ev.get("questions", [])
    assert 1 <= len(qs) <= 3, f"expected 1-3 suggestions, got {len(qs)}"
    tok = [e for e in events if e.get("type") == "token"]
    assert len(tok) == 0, f"'{vague}' should NOT stream tokens, got {len(tok)}"


# ── (3) CONTEXT ENRICHMENT: short follow-up uses prior topic ──
def test_context_enrichment_short_followup(admin_session):
    # Fresh conversation so prior context is clean
    r = admin_session.post(f"{BASE_URL}/api/chat/conversations",
                           json={"title": "TEST_iter8_ctx"}, timeout=20)
    cid = r.json()["_id"]
    try:
        _send(admin_session, cid, "how to configure GST in Biziverse?", timeout=60)
        events = _send(admin_session, cid, "how to do it", timeout=60)
        types = [e.get("type") for e in events]
        # Should be ambiguity-based suggestions OR direct GST-related answer — NOT a generic fallback
        joined = json.dumps(events).lower()
        assert ("gst" in joined or "ledger" in joined or "branch" in joined), \
            f"Follow-up did not pick up GST context. types={types} joined={joined[:300]}"
        # Specifically it should NOT be a pure 'no match' fallback only (a generic "I don't know")
        # If suggestions present, they should reference GST topic
        sug_ev = next((e for e in events if e.get("type") == "suggestions"), None)
        if sug_ev:
            qs = " | ".join(sug_ev.get("questions", [])).lower()
            assert "gst" in qs or "ledger" in qs or "tax" in qs, f"suggestions not GST-related: {qs}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (4a) GAP tracking source='suggestion' on ambiguous query ──
def test_gap_tracking_suggestion_source(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/chat/conversations",
                           json={"title": "TEST_iter8_gap_sug"}, timeout=20)
    cid = r.json()["_id"]
    unique_q = "extra charges"  # vague → suggestions (multiple KB items)
    try:
        _send(admin_session, cid, unique_q, timeout=60)
        # Fetch unanswered list
        g = admin_session.get(f"{BASE_URL}/api/admin/unanswered", timeout=20)
        assert g.status_code == 200
        data = g.json()
        pending = data.get("pending", []) if isinstance(data, dict) else data
        # Find an entry with conversation_id matching cid and source=suggestion
        match = [q for q in pending
                 if q.get("conversation_id") == cid and q.get("last_source") == "suggestion"]
        assert len(match) >= 1, f"No gap entry with source='suggestion' for conv {cid}. Found {len(pending)} total pending."
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (4b) GAP tracking source='fallback' on no-KB-match ──
def test_gap_tracking_fallback_source(admin_session):
    r = admin_session.post(f"{BASE_URL}/api/chat/conversations",
                           json={"title": "TEST_iter8_gap_fb"}, timeout=20)
    cid = r.json()["_id"]
    # Something that should NOT match KB or general questions
    nonsense = "zzqx random unrelated query about purple elephants xyzzy"
    try:
        _send(admin_session, cid, nonsense, timeout=90)
        g = admin_session.get(f"{BASE_URL}/api/admin/unanswered", timeout=20)
        data = g.json()
        pending = data.get("pending", []) if isinstance(data, dict) else data
        match = [q for q in pending
                 if q.get("conversation_id") == cid and q.get("last_source") == "fallback"]
        # Accept either fallback OR ai_uncertain (LLM might be invoked then return fallback marker)
        match_any = [q for q in pending
                     if q.get("conversation_id") == cid
                     and q.get("last_source") in ("fallback", "ai_uncertain")]
        assert len(match_any) >= 1, (
            f"No gap entry with source in (fallback, ai_uncertain) for conv {cid}. "
            f"All pending sources: {[q.get('last_source') for q in pending[:20]]}"
        )
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── Cleanup main module conv ──
def test_zz_cleanup(admin_session, conv_id):
    r = admin_session.delete(f"{BASE_URL}/api/chat/conversations/{conv_id}", timeout=15)
    assert r.status_code in (200, 204)

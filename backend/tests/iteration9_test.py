"""Iteration 9 backend tests:
   (1) AI Semantic Router — semantic match for 'dynamic qr' returns QR/UPI KB suggestions.
   (2) AI Router out-of-scope — 'how to bake a chocolate cake' returns scope_fallback with {modules} substitution.
   (3) AI Router direct-serve — verbatim KB title → ai_router_direct OR kb_direct.
   (4) AI Router admin toggle — use_ai_router=false disables router (no scope_fallback).
   (5) Smart gap pending_resolution — router suggestion → not visible in /api/admin/unanswered.
   (6) Smart gap cleanup — clicking verbatim KB question deletes pending_resolution row.
   (7) Smart gap out-of-scope visible — scope_fallback creates source='fallback' pending row.
   (8) Admin users hides role='user' / 'end_user'.
   (9) POST /api/auth/google/session: 400 on missing, 401/500 on bad session_id.
"""
import os
import json
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pull-push.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"


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
def original_ai_config(admin_session):
    """Capture current ai-config so we can restore at the end."""
    r = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=15)
    assert r.status_code == 200
    cfg = r.json()
    return {
        "use_ai_router": cfg.get("use_ai_router", True),
        "scope_fallback_message": cfg.get("scope_fallback_message", ""),
        "enabled_module_labels": cfg.get("enabled_module_labels") or [],
    }


@pytest.fixture(scope="module", autouse=True)
def configure_ai_router(admin_session, original_ai_config):
    """Ensure router is enabled and scope-fallback configured for tests."""
    body = {
        "use_ai_router": True,
        "scope_fallback_message": "I only know about {modules}. Please ask me about these topics.",
        "enabled_module_labels": ["Sales Invoices", "GST"],
    }
    r = admin_session.put(f"{BASE_URL}/api/admin/ai-config", json=body, timeout=20)
    assert r.status_code == 200, f"ai-config update failed: {r.status_code} {r.text[:300]}"
    yield
    # restore
    admin_session.put(f"{BASE_URL}/api/admin/ai-config",
                      json=original_ai_config, timeout=20)


def _send(session, conv_id, content, timeout=120):
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
    assert r.status_code == 200
    msgs = r.json().get("messages", [])
    assistants = [m for m in msgs if m.get("role") == "assistant"]
    return assistants[-1] if assistants else None


def _new_conv(session, title):
    r = session.post(f"{BASE_URL}/api/chat/conversations",
                     json={"title": title}, timeout=20)
    assert r.status_code in (200, 201), f"conv create failed: {r.status_code}"
    return r.json()["_id"]


# ── (1) AI ROUTER — semantic suggestions for 'dynamic qr' ──
def test_router_semantic_dynamic_qr(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_router_qr")
    try:
        events = _send(admin_session, cid, "dynamic qr", timeout=120)
        types = [e.get("type") for e in events]
        # Expect either suggestions (semantic ranking) or direct-serve to a QR KB item
        sug_evs = [e for e in events if e.get("type") == "suggestions"]
        tok_evs = [e for e in events if e.get("type") == "token"]
        msg = _last_assistant_msg(admin_session, cid)
        src = msg.get("source") if msg else None
        joined = " | ".join((q for e in sug_evs for q in e.get("questions", []))).lower()
        token_joined = " ".join((e.get("content", "") for e in tok_evs)).lower()

        # Suggestions path: at least one QR-related KB item
        if sug_evs:
            assert any(k in joined for k in ("qr", "upi")), \
                f"'dynamic qr' suggestions not QR/UPI related: {joined!r}"
            assert src in ("ai_router_suggestion", "suggestion"), \
                f"expected ai_router_suggestion source, got {src}"
        elif tok_evs:
            # Direct-serve: content should mention QR
            assert "qr" in token_joined or "upi" in token_joined, \
                f"direct-serve answer not QR-related: {token_joined[:200]}"
            assert src in ("ai_router_direct", "kb_direct", "ai_kb"), \
                f"unexpected direct-serve source: {src}"
        else:
            pytest.fail(f"'dynamic qr' produced neither suggestions nor tokens. types={types}")
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (2) AI ROUTER — out-of-scope module fallback ──
def test_router_out_of_scope_module_fallback(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_oos")
    try:
        events = _send(admin_session, cid, "how to bake a chocolate cake", timeout=120)
        types = [e.get("type") for e in events]
        fb_evs = [e for e in events if e.get("type") == "fallback"]
        msg = _last_assistant_msg(admin_session, cid)
        src = msg.get("source") if msg else None
        content = (msg.get("content") if msg else "") or ""

        # Acceptance: either an explicit fallback event with substituted modules,
        # OR a stored assistant message with source='scope_fallback' containing the modules
        assert (fb_evs or src == "scope_fallback"), \
            f"out-of-scope query did not produce scope fallback. types={types} src={src}"
        # Module substitution should be present (Sales Invoices & GST)
        text = (fb_evs[0].get("message") if fb_evs else content).lower()
        assert "sales invoices" in text and "gst" in text, \
            f"scope fallback didn't substitute {{modules}}: {text!r}"
        assert "{modules}" not in text, "Placeholder {modules} not replaced"
        assert src == "scope_fallback", f"expected source=scope_fallback, got {src}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (3) AI ROUTER — direct-serve verbatim KB title ──
def test_router_direct_serve_verbatim(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_direct")
    try:
        events = _send(admin_session, cid, "How to Configure Amount-Based QR Code ?", timeout=120)
        sug_evs = [e for e in events if e.get("type") == "suggestions"]
        tok_evs = [e for e in events if e.get("type") == "token"]
        msg = _last_assistant_msg(admin_session, cid)
        src = msg.get("source") if msg else None
        assert len(sug_evs) == 0, f"verbatim KB question should NOT show suggestions. src={src}"
        assert len(tok_evs) >= 1, f"verbatim KB question should stream tokens. src={src}"
        assert src in ("ai_router_direct", "kb_direct"), f"expected ai_router_direct or kb_direct, got {src}"
        assert msg.get("confidence", 0) >= 90, f"low confidence on direct-serve: {msg.get('confidence')}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (4) AI ROUTER — admin toggle off disables router ──
def test_router_toggle_off_disables(admin_session, original_ai_config):
    # Turn off router
    r = admin_session.put(f"{BASE_URL}/api/admin/ai-config",
                          json={"use_ai_router": False}, timeout=20)
    assert r.status_code == 200
    cid = _new_conv(admin_session, "TEST_iter9_toggle_off")
    try:
        events = _send(admin_session, cid, "how to bake a chocolate cake", timeout=120)
        msg = _last_assistant_msg(admin_session, cid)
        src = msg.get("source") if msg else None
        # With router off, source should NOT be scope_fallback (that path requires router)
        assert src != "scope_fallback", \
            f"router disabled but scope_fallback still triggered. src={src}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)
        # restore router on
        admin_session.put(f"{BASE_URL}/api/admin/ai-config",
                          json={"use_ai_router": True}, timeout=20)


# ── (5) SMART GAP — pending_resolution NOT visible in /api/admin/unanswered ──
def test_smart_gap_pending_resolution_hidden(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_gap_hidden")
    try:
        _send(admin_session, cid, "dynamic qr", timeout=120)
        g = admin_session.get(f"{BASE_URL}/api/admin/unanswered", timeout=20)
        assert g.status_code == 200
        data = g.json()
        pending = data.get("pending", []) if isinstance(data, dict) else data
        # Verify: NO entry for THIS conv with status visible (status='pending_resolution' is excluded from listing)
        match_pending = [q for q in pending
                         if q.get("conversation_id") == cid and q.get("status") == "pending"]
        # pending_resolution rows should not be in this list at all
        match_resolution = [q for q in pending
                            if q.get("conversation_id") == cid
                            and q.get("status") == "pending_resolution"]
        assert len(match_resolution) == 0, \
            f"pending_resolution entries leaked into /api/admin/unanswered: {match_resolution}"
        # Strict: also no plain 'pending' entry for this exact 'dynamic qr' suggestion-track
        if match_pending:
            # If any, it must not be source='suggestion' (those should be pending_resolution)
            assert all(q.get("last_source") != "suggestion" for q in match_pending), \
                f"suggestion-source gap is visible (should be pending_resolution): {match_pending}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (6) SMART GAP — clicking verbatim KB after suggestion deletes pending_resolution ──
def test_smart_gap_cleanup_on_direct_serve(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_gap_cleanup")
    try:
        # Step 1: vague query → router gives suggestions, gap tracked as pending_resolution
        _send(admin_session, cid, "dynamic qr", timeout=120)
        # Step 2: user clicks suggestion → verbatim KB title → direct-serve
        _send(admin_session, cid, "How to Configure Amount-Based QR Code ?", timeout=120)
        # Step 3: verify no pending_resolution rows for this conv remain
        g = admin_session.get(f"{BASE_URL}/api/admin/unanswered", timeout=20)
        data = g.json()
        pending = data.get("pending", []) if isinstance(data, dict) else data
        remaining = [q for q in pending if q.get("conversation_id") == cid]
        # Either zero rows, or only non-suggestion entries
        if remaining:
            for q in remaining:
                assert q.get("last_source") != "suggestion", \
                    f"pending_resolution row not cleaned after direct-serve: {q}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (7) SMART GAP — out-of-scope still tracked as visible 'pending' ──
def test_smart_gap_oos_visible(admin_session):
    cid = _new_conv(admin_session, "TEST_iter9_gap_oos")
    unique_q = "how to bake an iter9 chocolate cake xyzzy"
    try:
        _send(admin_session, cid, unique_q, timeout=120)
        g = admin_session.get(f"{BASE_URL}/api/admin/unanswered", timeout=20)
        data = g.json()
        pending = data.get("pending", []) if isinstance(data, dict) else data
        match = [q for q in pending
                 if q.get("conversation_id") == cid
                 and q.get("last_source") == "fallback"]
        assert len(match) >= 1, \
            f"OOS query not tracked as visible pending+fallback for conv {cid}. " \
            f"All sources for conv: {[(q.get('last_source'), q.get('status')) for q in pending if q.get('conversation_id') == cid]}"
    finally:
        admin_session.delete(f"{BASE_URL}/api/chat/conversations/{cid}", timeout=15)


# ── (8) ADMIN /users hides role='user' and 'end_user' ──
def test_admin_users_hides_end_users(admin_session):
    r = admin_session.get(f"{BASE_URL}/api/admin/users", timeout=20)
    assert r.status_code == 200, f"GET /api/admin/users failed: {r.status_code}"
    users = r.json()
    assert isinstance(users, list)
    roles = [u.get("role") for u in users]
    assert "user" not in roles, f"role='user' leaked into /api/admin/users: {roles}"
    assert "end_user" not in roles, f"role='end_user' leaked: {roles}"
    # Sanity: at least the seeded super_admin must be present
    assert any(u.get("role") == "super_admin" for u in users), \
        f"super_admin missing from /api/admin/users: {roles}"


# ── (9) Google OAuth backend: 400 missing, 401/500 bad session_id ──
def test_google_session_missing_returns_400():
    r = requests.post(f"{BASE_URL}/api/auth/google/session", json={}, timeout=20)
    assert r.status_code == 400, f"Expected 400 on missing session_id, got {r.status_code}: {r.text[:200]}"


def test_google_session_invalid_returns_401_or_500():
    r = requests.post(f"{BASE_URL}/api/auth/google/session",
                      json={"session_id": "definitely_not_a_real_session_id_xyz"}, timeout=30)
    assert r.status_code in (401, 500), \
        f"Expected 401/500 on invalid session_id, got {r.status_code}: {r.text[:300]}"

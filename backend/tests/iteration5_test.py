"""Iteration 5 backend tests:
- POST /api/admin/reset-data (super_admin only)
- GET /api/admin/messages/{id} (feedback enrichment)
- GET /api/chat/conversations respects ai_config.max_user_conversations (cap + cleanup)
- /api/admin/ai-config accepts max_user_conversations
- KB items preserved after reset
"""
import os
import time
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://pull-push.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@biziverse.com"
ADMIN_PASSWORD = "Admin@123"


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    token = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def user_session(admin_session):
    """Create a non-super_admin user (end_user) for 403 / overflow tests."""
    email = f"TEST_iter5_{int(time.time())}@example.com"
    password = "User@1234"
    payload = {"email": email, "password": password, "name": "iter5 user", "role": "end_user"}
    r = admin_session.post(f"{BASE_URL}/api/admin/users", json=payload, timeout=15)
    assert r.status_code == 200, f"user create failed: {r.text}"
    user_id = r.json()["_id"]
    s = requests.Session()
    token = _login(s, email, password)
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    yield s, user_id, email
    # cleanup
    admin_session.delete(f"{BASE_URL}/api/admin/users/{user_id}", timeout=10)


# 1. AI Config: max_user_conversations roundtrip
class TestMaxUserConversations:
    def test_get_ai_config_default(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=15)
        assert r.status_code == 200
        cfg = r.json()
        # field may or may not be present yet; just sanity check call works
        assert isinstance(cfg, dict)

    def test_update_max_user_conversations(self, admin_session):
        r = admin_session.put(
            f"{BASE_URL}/api/admin/ai-config",
            json={"max_user_conversations": 3},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        cfg = r.json()
        assert cfg.get("max_user_conversations") == 3

        # GET reflects the update
        r2 = admin_session.get(f"{BASE_URL}/api/admin/ai-config", timeout=15)
        assert r2.json().get("max_user_conversations") == 3


# 2. GET /api/chat/conversations respects max_user_conversations + auto-cleans overflow
class TestConversationLimit:
    def test_overflow_truncated_and_cleaned(self, admin_session, user_session):
        s, user_id, _email = user_session
        # set limit to 3
        r = admin_session.put(
            f"{BASE_URL}/api/admin/ai-config", json={"max_user_conversations": 3}, timeout=15
        )
        assert r.status_code == 200

        # Create 5 conversations as this user
        ids = []
        for i in range(5):
            r = s.post(
                f"{BASE_URL}/api/chat/conversations",
                json={"title": f"TEST_iter5_conv_{i}"},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            ids.append(r.json()["_id"])
            time.sleep(0.05)

        # GET should return at most 3
        r = s.get(f"{BASE_URL}/api/chat/conversations", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) <= 3, f"Expected <=3, got {len(data)}"

        # call again — overflow already deleted; still <=3
        r = s.get(f"{BASE_URL}/api/chat/conversations", timeout=15)
        assert len(r.json()) <= 3


# 3. /api/admin/messages/{id} — enrichment endpoint
class TestMessageDetail:
    def test_invalid_id_returns_4xx(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/messages/notavalidid", timeout=10)
        assert r.status_code in (400, 404)

    def test_missing_id_returns_404(self, admin_session):
        # valid ObjectId format but does not exist
        r = admin_session.get(f"{BASE_URL}/api/admin/messages/507f1f77bcf86cd799439011", timeout=10)
        assert r.status_code == 404


# 4. /api/admin/reset-data — super_admin only
class TestResetData:
    def test_non_super_admin_forbidden(self, user_session):
        s, _uid, _e = user_session
        r = s.post(f"{BASE_URL}/api/admin/reset-data", timeout=15)
        assert r.status_code == 403

    def test_super_admin_can_reset_and_kb_preserved(self, admin_session):
        # Snapshot KB counts BEFORE
        r_an_before = admin_session.get(f"{BASE_URL}/api/admin/analytics", timeout=15)
        assert r_an_before.status_code == 200
        kb_items_before = r_an_before.json().get("total_knowledge_items", 0)
        modules_before = r_an_before.json().get("total_modules", 0)

        # Trigger reset
        r = admin_session.post(f"{BASE_URL}/api/admin/reset-data", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "deleted" in body
        deleted = body["deleted"]
        for k in ("conversations", "messages", "feedback", "tickets", "unanswered_questions"):
            assert k in deleted
            assert isinstance(deleted[k], int)

        # KB preserved
        r_an_after = admin_session.get(f"{BASE_URL}/api/admin/analytics", timeout=15)
        assert r_an_after.status_code == 200
        an = r_an_after.json()
        assert an.get("total_knowledge_items", 0) == kb_items_before
        assert an.get("total_modules", 0) == modules_before
        # transactional counts zeroed
        assert an.get("total_questions", 0) == 0
        assert an.get("total_conversations", 0) == 0
        assert an.get("total_feedback", 0) == 0
        assert an.get("open_tickets", 0) == 0


# 5. Regression: KB Export still works (iteration 4 surface)
class TestKBExportRegression:
    def test_export_kb(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/knowledge/export", timeout=20)
        # endpoint may be under /api/admin/knowledge/export OR /api/knowledge/export
        if r.status_code == 404:
            r = admin_session.get(f"{BASE_URL}/api/knowledge/export", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # should have modules/items at minimum
        assert any(k in data for k in ("modules", "items", "counts"))


# 6. Tickets endpoint still exists (used by user-side fallback)
class TestTicketsBackendStillExists:
    def test_admin_tickets_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/tickets", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

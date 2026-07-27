"""בדיקות אבטחה: CSRF, הגנת מנהל אחרון, כלי מיגרציה חסומים כברירת מחדל."""
import re


def _get_csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None


def test_csrf_blocks_request_without_token(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    r = client.post("/login", data={"username": "admin", "password": "Admin@2026!"})
    assert r.status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False


def test_csrf_allows_request_with_valid_token(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    page = client.get("/login")
    token = _get_csrf(page.get_data(as_text=True))
    r = client.post("/login", data={
        "username": "admin", "password": "Admin@2026!", "csrf_token": token
    })
    assert r.status_code in (200, 302)
    app.config["WTF_CSRF_ENABLED"] = False


def test_migration_routes_blocked_without_env_flags(client, monkeypatch):
    monkeypatch.delenv("ENABLE_ADMIN_TOOLS", raising=False)
    monkeypatch.delenv("MIGRATION_SECRET", raising=False)
    for path in ["/fix-db", "/rescue", "/upgrade-permissions"]:
        r = client.get(path)
        assert r.status_code == 403


def test_migration_routes_open_with_correct_flags(client, monkeypatch):
    monkeypatch.setenv("ENABLE_ADMIN_TOOLS", "true")
    monkeypatch.setenv("MIGRATION_SECRET", "testsecret123")
    r = client.get("/rescue?key=testsecret123")
    assert r.status_code == 200
    r_wrong = client.get("/rescue?key=wrongkey")
    assert r_wrong.status_code == 403


def test_cannot_delete_last_admin(client, db_session):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()

    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    r = client.post(f"/admin/delete_user/{admin.id}", follow_redirects=True)

    assert User.query.get(admin.id) is not None


def test_cannot_demote_last_admin(client, db_session):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()

    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    client.post(f"/admin/user/{admin.id}/edit", data={
        "username": admin.username, "email": admin.email, "role": "employee",
        "department_id": "", "manager_id": "", "password": "",
    })

    refreshed = User.query.get(admin.id)
    assert refreshed.role == "admin"


def test_reset_password_pages_render(client):
    assert client.get("/reset_password").status_code == 200

"""בדיקות: כלי אבחון מייל, וגלוי כשלי שליחה בממשק (SOS, הודעות קבוצתיות, הקצאת משימה)."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_test_email_route_requires_admin(client, db_session):
    from app.models.user import User

    emp = User(username="notadmin", email="notadmin@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "notadmin", "password": "x"})
    r = client.post("/admin/test_email")
    assert r.status_code == 403


def test_test_email_route_requires_admin_has_email(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    admin.email = None
    db_session.commit()

    r = client.post("/admin/test_email")
    data = r.get_json()
    assert data["success"] is False
    assert "כתובת מייל" in data["message"]


def test_test_email_route_reports_success_with_mail_suppressed(app, client, db_session):
    """כש-Flask-Mail במצב suppress (כמו בבדיקות), 'שליחה' מצליחה בלי SMTP אמיתי."""
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "smtp.office365.com"
    app.config["MAIL_USERNAME"] = "test@company.com"
    app.config["MAIL_PASSWORD"] = "fakepassword"

    r = client.post("/admin/test_email")
    data = r.get_json()
    assert data["success"] is True
    assert "admin@taskmanager.local" in data["message"]


def test_test_email_route_reports_real_failure(app, client, db_session, monkeypatch):
    """מדמה בדיוק את המצב שקרה בפרודקשן: MAIL_SERVER לא מוגדר/לא נגיש -> כשל אמיתי, מדווח בבירור."""
    from app import mail

    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "smtp.office365.com"
    app.config["MAIL_USERNAME"] = "test@company.com"
    app.config["MAIL_PASSWORD"] = "fakepassword"

    # מכבים את מצב ה-suppress כדי לדמות ניסיון חיבור אמיתי לשרת שלא קיים (כמו MAIL_SERVER='localhost' בפרודקשן)
    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    try:
        r = client.post("/admin/test_email")
        data = r.get_json()
        assert data["success"] is False
        assert "התחברות" in data["message"] or "נכשל" in data["message"] or "שגיאת" in data["message"]
    finally:
        app.extensions["mail"].suppress = original_suppress


def test_task_assignment_flashes_warning_when_email_fails(app, client, db_session):
    """הבאג המקורי: כשל מייל היה סמוי לגמרי מהמשתמש. עכשיו הוא אמור להופיע כ-flash danger."""
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="failmailemp", email="failmailemp@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    try:
        r = client.post("/", data={
            "title": "משימה עם כשל מייל צפוי", "description": "", "priority": "LOW",
            "assigned_to_id": str(emp.id), "recurrence": "NONE",
        }, follow_redirects=True)
        body = r.get_data(as_text=True)
        assert "שליחת המייל" in body and "נכשלה" in body
    finally:
        app.extensions["mail"].suppress = original_suppress


def test_sos_response_includes_email_failed_list(app, client, db_session):
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    emp = User(username="sosfailemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    try:
        client.post("/login", data={"username": "sosfailemp", "password": "x"})
        r = client.post("/sos", data={"message": "בדיקה"})
        data = r.get_json()
        assert "email_failed_to" in data
        assert "admin" in data["email_failed_to"]
    finally:
        app.extensions["mail"].suppress = original_suppress

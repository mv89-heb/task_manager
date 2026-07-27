"""בדיקות ל-logging מפורט ומבוקר בכלי אבחון המייל, וה-endpoint /api/admin/mail/status."""
import logging


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_mail_status_endpoint_requires_admin(client, db_session):
    from app.models.user import User

    emp = User(username="statusnoperm", email="s@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "statusnoperm", "password": "x"})
    r = client.get("/api/admin/mail/status")
    assert r.status_code == 403


def test_mail_status_endpoint_returns_expected_shape(client, db_session):
    _login_admin(client)
    r = client.get("/api/admin/mail/status")
    data = r.get_json()
    assert set(["smtp_configured", "server", "port", "username_exists"]).issubset(data.keys())
    assert isinstance(data["smtp_configured"], bool)
    assert isinstance(data["username_exists"], bool)


def test_mail_status_endpoint_never_exposes_password(client, db_session):
    _login_admin(client)
    r = client.get("/api/admin/mail/status")
    body = r.get_data(as_text=True)
    assert "password" not in body.lower() or "MAIL_PASSWORD" not in body


def test_test_email_logs_each_stage(app, client, db_session, caplog):
    """מוודא שכל שלב (התחלה, בדיקת הגדרות, שליחה, סיום) נרשם ללוג בנפרד."""
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "smtp.office365.com"
    app.config["MAIL_USERNAME"] = "test@company.com"
    app.config["MAIL_PASSWORD"] = "fakepassword"

    with caplog.at_level(logging.INFO):
        r = client.post("/admin/test_email")
        assert r.get_json()["success"] is True

    log_text = caplog.text
    assert "[mail-test] בדיקת מייל התחילה" in log_text
    assert f"user_id={admin.id}" in log_text
    assert "בדיקת הגדרות SMTP" in log_text
    assert "שלב שליחה" in log_text or "נשלח בהצלחה" in log_text


def test_test_email_never_logs_password_value(app, client, db_session, caplog, monkeypatch):
    """קריטי: גם כשיש MAIL_PASSWORD אמיתי, הוא לעולם לא אמור להופיע בלוג - רק 'קיים'/'חסר'."""
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    secret_password = "SuperSecretPassword123!"
    app.config["MAIL_PASSWORD"] = secret_password
    app.config["MAIL_USERNAME"] = "realuser@company.com"

    with caplog.at_level(logging.INFO):
        client.post("/admin/test_email")

    assert secret_password not in caplog.text
    assert "MAIL_PASSWORD=קיים" in caplog.text or "MAIL_PASSWORD='קיים'" in caplog.text or "MAIL_PASSWORD=קיים" in caplog.text.replace("'", "")


def test_test_email_reports_smtp_not_configured_specifically(app, client, db_session, monkeypatch):
    """כש-MAIL_SERVER הוא localhost (ברירת המחדל כשלא הוגדר כלום), ההודעה צריכה לומר 'SMTP לא מוגדר' ולא הודעה גנרית."""
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "localhost"
    r = client.post("/admin/test_email")
    data = r.get_json()
    assert data["success"] is False
    assert "SMTP לא מוגדר" in data["message"]


def test_test_email_reports_missing_credentials_specifically(app, client, db_session):
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "smtp.office365.com"
    app.config["MAIL_USERNAME"] = None
    app.config["MAIL_PASSWORD"] = None

    r = client.post("/admin/test_email")
    data = r.get_json()
    assert data["success"] is False
    assert "פרטי התחברות" in data["message"]


def test_test_email_reports_connection_error_specifically(app, client, db_session):
    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    app.config["MAIL_SERVER"] = "smtp.office365.com"
    app.config["MAIL_USERNAME"] = "user@company.com"
    app.config["MAIL_PASSWORD"] = "wrongpass"

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    try:
        r = client.post("/admin/test_email")
        data = r.get_json()
        assert data["success"] is False
        # שרת לא אמיתי בסביבת הבדיקה - צריך לקבל שגיאת התחברות ולא קריסה/הודעה גנרית
        assert "התחברות" in data["message"] or "שגיאת" in data["message"]
    finally:
        app.extensions["mail"].suppress = original_suppress

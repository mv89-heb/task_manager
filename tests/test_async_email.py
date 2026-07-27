"""בדיקות: שליחת מייל תמיד רצה ברקע (thread נפרד) ולא חוסמת את הבקשה -
זה מה שתיקן את התקיעות הארוכה בטופס הדיווח הציבורי כשאין SMTP מוגדר."""
import time


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_public_report_responds_fast_even_with_unreachable_smtp(app, client, db_session):
    """הבדיקה המרכזית לתיקון: גם עם SMTP לא נגיש (מדמה בדיוק את מה שקרה בפרודקשן),
    הבקשה חוזרת תוך שנייה-שתיים, לא נתקעת לעשרות שניות."""
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    # מכבים suppress ומצביעים לשרת לא נגיש - בדיוק המצב שגרם לתקיעות בפרודקשן
    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    app.config["MAIL_SERVER"] = "10.255.255.1"  # כתובת לא נגישה (RFC 5737 test range behavior) - תיפול/תתעכב
    app.config["MAIL_PORT"] = 25

    try:
        start = time.time()
        r = client.post("/report", data={"title": "בדיקת מהירות תגובה", "description": ""})
        elapsed = time.time() - start

        assert r.status_code in (200, 302)
        assert elapsed < 3, f"הבקשה לקחה {elapsed:.1f} שניות - אמורה לחזור כמעט מיידית"
    finally:
        app.extensions["mail"].suppress = original_suppress
        app.config["MAIL_SERVER"] = "localhost"


def test_email_eventually_sent_via_background_thread(app, client, db_session):
    """מוודא שהמייל בכל זאת *כן* נשלח בפועל, רק לא חוסם את הבקשה."""
    from app import mail
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    with mail.record_messages() as outbox:
        client.post("/report", data={"title": "בדיקת שליחה בפועל ברקע", "description": ""})
        # נותנים לthread הרקע רגע להשלים (suppress=True אז זה מיידי כמעט, אבל עדיין thread נפרד)
        time.sleep(0.3)
        assert len(outbox) == 1
        assert "בדיקת שליחה בפועל ברקע" in outbox[0].subject


def test_sos_email_does_not_block_response(app, client, db_session):
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    emp = User(username="asyncsosemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    app.config["MAIL_SERVER"] = "10.255.255.1"
    app.config["MAIL_PORT"] = 25

    try:
        client.post("/login", data={"username": "asyncsosemp", "password": "x"})
        start = time.time()
        r = client.post("/sos", data={"message": "בדיקת מהירות SOS"})
        elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 3, f"SOS לקח {elapsed:.1f} שניות - אמור לחזור מיידית"
    finally:
        app.extensions["mail"].suppress = original_suppress
        app.config["MAIL_SERVER"] = "localhost"


def test_bulk_message_email_does_not_block_response(app, client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="asyncbulkemp", email="asyncbulkemp@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    app.config["MAIL_SERVER"] = "10.255.255.1"
    app.config["MAIL_PORT"] = 25

    try:
        start = time.time()
        r = client.post("/send_bulk_message", data={
            "recipient_ids": [str(emp.id)], "message": "בדיקת מהירות הודעה קבוצתית", "send_email": "1",
        })
        elapsed = time.time() - start

        assert r.status_code == 200
        assert elapsed < 3
    finally:
        app.extensions["mail"].suppress = original_suppress
        app.config["MAIL_SERVER"] = "localhost"


def test_task_assignment_email_does_not_block_response(app, client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="asynctaskemp", email="asynctaskemp@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False
    app.config["MAIL_SERVER"] = "10.255.255.1"
    app.config["MAIL_PORT"] = 25

    try:
        start = time.time()
        r = client.post("/", data={
            "title": "בדיקת מהירות הקצאה", "description": "", "priority": "LOW",
            "assigned_to_id": str(emp.id), "recurrence": "NONE",
        })
        elapsed = time.time() - start

        assert r.status_code in (200, 302)
        assert elapsed < 3
    finally:
        app.extensions["mail"].suppress = original_suppress
        app.config["MAIL_SERVER"] = "localhost"


def test_slow_smtp_never_blocks_the_request_deterministic(app, client, db_session, monkeypatch):
    """
    בדיקה דטרמיניסטית שלא תלויה בהתנהגות רשת אמיתית: מדמים SMTP איטי בכוונה
    (2 שניות עיכוב מלאכותי) ומוודאים שהבקשה עדיין חוזרת כמעט מיידית, כי השליחה
    רצה ב-thread נפרד ולא בתוך thread הבקשה עצמו.
    """
    from app.models.user import User
    import flask_mail
    import time as time_module

    admin = User.query.filter_by(role="admin").first()
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    original_suppress = app.extensions["mail"].suppress
    app.extensions["mail"].suppress = False

    def slow_send(self, message):
        time_module.sleep(2)  # מדמה שרת SMTP איטי/תקוע

    monkeypatch.setattr(flask_mail.Mail, "send", slow_send)

    try:
        start = time_module.time()
        r = client.post("/report", data={"title": "בדיקת SMTP איטי מדומה", "description": ""})
        elapsed = time_module.time() - start

        assert r.status_code in (200, 302)
        assert elapsed < 1.5, (
            f"הבקשה לקחה {elapsed:.2f} שניות למרות ש-mail.send מדומה לוקח 2 שניות - "
            "משמע השליחה עדיין רצה בתוך thread הבקשה ולא ברקע!"
        )
    finally:
        app.extensions["mail"].suppress = original_suppress

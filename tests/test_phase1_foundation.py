"""
בדיקות Phase 1 - System Audit & Foundation:
- 4 ה-routes שנמצאו בביקורת בלי כיסוי ישיר (calendar_tasks, update_status, mark_all_read, calendar page)
- עקביות: kanban/calendar מחריגים דיווחים ציבוריים (התיקון שנמצא בביקורת)
- אינדקסים נוצרים בפועל
- הגנת _validate_identifier
- הלוגיקה המשותפת של notify_recipients_multi_channel
"""
from datetime import date


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


# ---------- 4 הבדיקות החסרות שהביקורת מצאה ----------

def test_calendar_page_loads(client, db_session):
    _login_admin(client)
    r = client.get("/calendar")
    assert r.status_code == 200


def test_calendar_tasks_api_returns_events(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="משימה ליומן", user_id=admin.id, assigned_to_id=admin.id, due_date=date.today())
    db_session.add(task)
    db_session.commit()

    r = client.get("/api/calendar_tasks")
    assert r.status_code == 200
    data = r.get_json()
    titles = [e["title"] for e in data]
    assert "משימה ליומן" in titles


def test_update_status_endpoint_changes_status(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="לעדכון סטטוס ישיר", user_id=admin.id, assigned_to_id=admin.id, status="TODO")
    db_session.add(task)
    db_session.commit()

    r = client.post(f"/update_status/{task.id}", json={"status": "IN_PROGRESS"})
    assert r.status_code == 200
    assert r.get_json()["success"] is True

    refreshed = Task.query.get(task.id)
    assert refreshed.status == "IN_PROGRESS"


def test_notifications_mark_all_read_endpoint(client, db_session):
    from app.models.notification import Notification, notify

    admin = _login_admin(client)
    notify(admin.id, "בדיקה 1")
    notify(admin.id, "בדיקה 2")
    assert Notification.query.filter_by(user_id=admin.id, is_read=False).count() == 2

    r = client.post("/notifications/mark_all_read")
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    assert Notification.query.filter_by(user_id=admin.id, is_read=False).count() == 0


# ---------- תיקון עקביות: kanban/calendar מחריגים דיווחים ציבוריים ----------

def test_kanban_excludes_public_reports(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    client.post("/report", data={"title": "דיווח שלא בקנבן", "description": ""})
    db_session.add(Task(title="משימה פנימית בקנבן", user_id=admin.id, assigned_to_id=admin.id, source="internal"))
    db_session.commit()

    r = client.get("/kanban")
    body = r.get_data(as_text=True)
    assert "משימה פנימית בקנבן" in body
    assert "דיווח שלא בקנבן" not in body


def test_calendar_tasks_excludes_public_reports(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)

    # דיווח ציבורי עם תאריך יעד (מקרה קצה - אם מישהו יערוך דיווח ויוסיף תאריך)
    client.post("/report", data={"title": "דיווח עם תאריך", "description": ""})
    reported = Task.query.filter_by(title="דיווח עם תאריך").first()
    reported.due_date = date.today()
    db_session.commit()

    internal = Task(title="משימה פנימית עם תאריך", user_id=admin.id, assigned_to_id=admin.id, due_date=date.today())
    db_session.add(internal)
    db_session.commit()

    r = client.get("/api/calendar_tasks")
    titles = [e["title"] for e in r.get_json()]
    assert "משימה פנימית עם תאריך" in titles
    assert "דיווח עם תאריך" not in titles


# ---------- אינדקסים נוצרו בפועל ----------

def test_performance_indexes_exist(app, db_session):
    from sqlalchemy import text
    from app import db

    expected = {
        'ix_task_assigned_to_id', 'ix_task_status', 'ix_task_source',
        'ix_task_department_id', 'ix_notification_user_id', 'ix_user_department_id',
    }
    with app.app_context():
        rows = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='index'")).fetchall()
    names = {r[0] for r in rows}
    missing = expected - names
    assert not missing, f"אינדקסים חסרים: {missing}"


# ---------- הגנת _validate_identifier ----------

def test_validate_identifier_blocks_sql_injection_attempt():
    from app import _validate_identifier
    import pytest

    with pytest.raises(ValueError):
        _validate_identifier("task; DROP TABLE user; --")

    with pytest.raises(ValueError):
        _validate_identifier("col' OR '1'='1")

    with pytest.raises(ValueError):
        _validate_identifier("")


def test_validate_identifier_accepts_normal_names():
    from app import _validate_identifier

    assert _validate_identifier("department_id") == "department_id"
    assert _validate_identifier("ix_task_status") == "ix_task_status"


# ---------- הלוגיקה המשותפת (notify_recipients_multi_channel) ----------

def test_notify_recipients_multi_channel_used_by_sos_and_bulk_message(client, db_session):
    """בדיקת רגרסיה שהמיחזור לא שינה התנהגות: SOS והודעה קבוצתית עדיין עובדים כרגיל."""
    from app.models.user import User
    from app.models.notification import Notification

    admin = _login_admin(client)
    admin.email = "admin@taskmanager.local"
    db_session.commit()

    emp = User(username="phase1sosemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.get("/logout")
    client.post("/login", data={"username": "phase1sosemp", "password": "x"})
    r = client.post("/sos", data={"message": "בדיקת מיחזור SOS"})
    data = r.get_json()
    assert data["success"] is True
    assert "admin" in data["email_sent_to"]

    notif = Notification.query.filter_by(user_id=admin.id).first()
    assert notif is not None
    assert "phase1sosemp" in notif.message


def test_bulk_message_still_respects_channel_toggles_after_refactor(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    emp = User(username="phase1bulkemp", email="phase1bulkemp@test.com", role="employee", phone="0501112233")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    r = client.post("/send_bulk_message", data={
        "recipient_ids": [str(emp.id)], "message": "בדיקת טוגלים אחרי מיחזור",
        "send_email": "1", "send_whatsapp": "0",
    })
    data = r.get_json()
    assert data["success"] is True
    assert "phase1bulkemp" in data["email_sent_to"]
    assert data["whatsapp_targets"] == []  # send_whatsapp=0 - לא אמור להופיע קישור

"""בדיקות: מייל אוטומטי בהקצאת משימה, ותזכורות יומיות (מייל + מערכת)."""
from datetime import date, timedelta


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_new_task_assignment_sends_email(app, client, db_session):
    from app.models.user import User
    from app import mail

    admin = _login_admin(client)
    emp = User(username="mailemp", email="mailemp@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    with mail.record_messages() as outbox:
        client.post("/", data={
            "title": "משימה עם מייל אוטומטי", "description": "", "priority": "LOW",
            "assigned_to_id": str(emp.id), "recurrence": "NONE",
        })
        assert len(outbox) == 1
        assert outbox[0].recipients == ["mailemp@test.com"]
        assert "משימה עם מייל אוטומטי" in outbox[0].subject


def test_new_task_assignment_no_email_if_recipient_has_none(app, client, db_session):
    from app.models.user import User
    from app import mail

    admin = _login_admin(client)
    emp = User(username="noemailemp", role="employee")  # no email
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    with mail.record_messages() as outbox:
        r = client.post("/", data={
            "title": "משימה בלי מייל", "description": "", "priority": "LOW",
            "assigned_to_id": str(emp.id), "recurrence": "NONE",
        })
        assert r.status_code in (200, 302)
        assert len(outbox) == 0  # לא אמור לקרוס, פשוט לא שולח


def test_reassignment_sends_email(app, client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from app import mail

    admin = _login_admin(client)
    original = User(username="origassignee", role="employee")
    original.set_password("x")
    new_assignee = User(username="newassignee", email="newassignee@test.com", role="employee")
    new_assignee.set_password("x")
    db_session.add_all([original, new_assignee])
    db_session.commit()

    task = Task(title="בדיקת שיוך מחדש", user_id=admin.id, assigned_to_id=original.id)
    db_session.add(task)
    db_session.commit()

    with mail.record_messages() as outbox:
        client.post(f"/edit/{task.id}", data={
            "title": "בדיקת שיוך מחדש", "description": "", "priority": "LOW", "status": "TODO",
            "assigned_to_id": str(new_assignee.id), "recurrence": "NONE",
        })
        assert len(outbox) == 1
        assert outbox[0].recipients == ["newassignee@test.com"]


def test_no_email_when_assigning_task_to_self(app, client, db_session):
    from app import mail

    admin = _login_admin(client)
    with mail.record_messages() as outbox:
        client.post("/", data={
            "title": "משימה לעצמי", "description": "", "priority": "LOW",
            "assigned_to_id": str(admin.id), "recurrence": "NONE",
        })
        assert len(outbox) == 0


def test_reminders_today_includes_only_todays_tasks(app, client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.task import Task
    from app.models.notification import Notification
    from app import mail

    monkeypatch.setenv("REMINDER_SECRET", "testsecret")

    admin = User.query.filter_by(role="admin").first()
    emp = User(username="remindtoday", email="remindtoday@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    today_task = Task(title="להיום", user_id=admin.id, assigned_to_id=emp.id, due_date=date.today(), status="TODO")
    tomorrow_task = Task(title="למחר", user_id=admin.id, assigned_to_id=emp.id, due_date=date.today() + timedelta(days=1), status="TODO")
    db_session.add_all([today_task, tomorrow_task])
    db_session.commit()

    with mail.record_messages() as outbox:
        r = client.get("/api/send_due_reminders?key=testsecret&when=today")
        data = r.get_json()
        assert data["found"] == 1
        assert data["notified"] == 1
        assert len(outbox) == 1
        assert "להיום" in outbox[0].subject

    notif = Notification.query.filter_by(user_id=emp.id).first()
    assert notif is not None
    assert "להיום" in notif.message


def test_reminders_tomorrow_mode(app, client, db_session, monkeypatch):
    from app.models.user import User
    from app.models.task import Task

    monkeypatch.setenv("REMINDER_SECRET", "testsecret2")

    admin = User.query.filter_by(role="admin").first()
    emp = User(username="remindtmrw", email="remindtmrw@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    db_session.add(Task(title="למחר בדיוק", user_id=admin.id, assigned_to_id=emp.id,
                         due_date=date.today() + timedelta(days=1), status="TODO"))
    db_session.commit()

    r = client.get("/api/send_due_reminders?key=testsecret2&when=tomorrow")
    data = r.get_json()
    assert data["found"] == 1
    assert data["when"] == "tomorrow"


def test_reminders_route_blocked_without_key(client):
    r = client.get("/api/send_due_reminders")
    assert r.status_code == 403


def test_dashboard_shows_whatsapp_reminder_button_when_assignee_has_phone(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from datetime import date

    admin = _login_admin(client)
    emp = User(username="whatsappable", phone="0501234567", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    db_session.add(Task(title="עם וואטסאפ", user_id=admin.id, assigned_to_id=emp.id, due_date=date.today(), status="TODO"))
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "wa.me/972501234567" in body


def test_dashboard_hides_whatsapp_button_without_phone(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from datetime import date

    admin = _login_admin(client)
    emp = User(username="nowhatsapp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    db_session.add(Task(title="בלי וואטסאפ", user_id=admin.id, assigned_to_id=emp.id, due_date=date.today(), status="TODO"))
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "wa.me/" not in body

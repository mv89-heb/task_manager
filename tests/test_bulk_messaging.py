"""בדיקות לשליחת הודעות קבוצתיות (מייל/וואטסאפ) למשתמשים נבחרים/מחלקה/ארגון."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_bulk_message_to_specific_users(client, db_session):
    from app.models.user import User
    from app.models.notification import Notification

    admin = _login_admin(client)
    u1 = User(username="bulk1", email="bulk1@test.com", role="employee")
    u1.set_password("x")
    u2 = User(username="bulk2", phone="0501112233", role="employee")
    u2.set_password("x")
    db_session.add_all([u1, u2])
    db_session.commit()

    r = client.post("/send_bulk_message", data={
        "recipient_ids": [str(u1.id), str(u2.id)],
        "message": "עדכון חשוב לצוות",
        "send_email": "1",
        "send_whatsapp": "1",
    })
    data = r.get_json()
    assert data["success"] is True
    assert data["notified_count"] == 2
    assert "bulk2" in [t["name"] for t in data["whatsapp_targets"]]

    assert Notification.query.filter_by(user_id=u1.id).first() is not None
    assert Notification.query.filter_by(user_id=u2.id).first() is not None


def test_bulk_message_blocks_recipient_outside_scope(client, db_session):
    """מנהל תחום לא יכול לשלוח הודעה למישהו מחוץ למחלקה שלו, גם אם ה-id הועבר ידנית."""
    from app.models.user import User
    from app.models.department import Department

    dept_a = Department(name="מחלקה א הודעות")
    dept_b = Department(name="מחלקה ב הודעות")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    mgr = User(username="msgmgr", role="manager", department_id=dept_a.id)
    mgr.set_password("x")
    outsider = User(username="msgoutsider", email="out@test.com", role="employee", department_id=dept_b.id)
    outsider.set_password("x")
    db_session.add_all([mgr, outsider])
    db_session.commit()

    client.post("/login", data={"username": "msgmgr", "password": "x"})
    r = client.post("/send_bulk_message", data={
        "recipient_ids": [str(outsider.id)],
        "message": "ניסיון עקיפה",
        "send_email": "1",
    })
    data = r.get_json()
    assert data["success"] is False


def test_employee_cannot_send_bulk_message(client, db_session):
    from app.models.user import User

    emp = User(username="regularemp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "regularemp", "password": "x"})
    r = client.post("/send_bulk_message", data={"recipient_ids": ["1"], "message": "test", "send_email": "1"})
    assert r.status_code == 403


def test_bulk_message_requires_at_least_one_channel(client, db_session):
    from app.models.user import User

    admin = _login_admin(client)
    u1 = User(username="nochannel", email="nc@test.com", role="employee")
    u1.set_password("x")
    db_session.add(u1)
    db_session.commit()

    r = client.post("/send_bulk_message", data={
        "recipient_ids": [str(u1.id)], "message": "test",
        "send_email": "0", "send_whatsapp": "0",
    })
    data = r.get_json()
    assert data["success"] is False


def test_messaging_modal_renders_for_manager_with_department(client, db_session):
    from app.models.user import User
    from app.models.department import Department

    dept = Department(name="מחלקת תצוגה")
    db_session.add(dept)
    db_session.commit()

    mgr = User(username="viewmgr", role="manager", department_id=dept.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/login", data={"username": "viewmgr", "password": "x"})
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert 'id="messageModal"' in body
    assert "מחלקת תצוגה" in body
    # מנהל תחום לא אמור לראות את הכפתור למצב "כל הארגון" (רק admin רואה אותו)
    assert 'data-mode="org"' not in body

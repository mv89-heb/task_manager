"""בדיקות: התחברות לפי שם משתמש (לא מייל), מייל/טלפון אופציונליים, ותכונת SOS רב-ערוצית."""


def test_login_by_username_works(client, app):
    from app.models.user import User
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        username = admin.username
    r = client.post("/login", data={"username": username, "password": "Admin@2026!"}, follow_redirects=True)
    assert r.status_code == 200
    assert "logout" in r.get_data(as_text=True).lower() or r.request.path == "/"


def test_login_with_email_field_fails(client, app):
    """מוודא שהתחברות עם 'email' כשם שדה כבר לא עובדת - username הוא השדה הנכון עכשיו."""
    from app.models.user import User
    with app.app_context():
        admin = User.query.filter_by(role="admin").first()
        admin_email = admin.email
    r = client.post("/login", data={"email": admin_email, "password": "Admin@2026!"}, follow_redirects=True)
    # השדה email לא קיים בטופס יותר - הבקשה לא תתחבר בהצלחה
    body = r.get_data(as_text=True)
    assert "לא נכונים" in body or "שם משתמש" in body


def test_register_without_email_or_phone(client, db_session):
    from app.models.user import User

    r = client.post("/register", data={"username": "noemail_user", "password": "x"}, follow_redirects=True)
    user = User.query.filter_by(username="noemail_user").first()
    assert user is not None
    assert user.email is None
    assert user.phone is None


def test_register_with_phone_only(client, db_session):
    from app.models.user import User

    client.post("/register", data={"username": "phoneonly_user", "phone": "0501234567", "password": "x"})
    user = User.query.filter_by(username="phoneonly_user").first()
    assert user is not None
    assert user.phone == "0501234567"
    assert user.email is None


def test_whatsapp_link_converts_israeli_local_format():
    from app.models.user import User
    u = User(username="wa_test", phone="050-1234567")
    link = u.whatsapp_link("שלום")
    assert link is not None
    assert "972501234567" in link
    assert link.startswith("https://wa.me/")


def test_whatsapp_link_none_without_phone():
    from app.models.user import User
    u = User(username="no_phone")
    assert u.whatsapp_link("test") is None


def test_sos_notifies_admin_when_no_manager(client, db_session):
    from app.models.user import User
    from app.models.notification import Notification

    admin = User.query.filter_by(role="admin").first()
    emp = User(username="sos_emp", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "sos_emp", "password": "x"})
    r = client.post("/sos", data={"message": "יש דליפת מים דחופה"})
    data = r.get_json()

    assert data["success"] is True
    assert data["recipient_count"] >= 1

    notif = Notification.query.filter_by(user_id=admin.id).first()
    assert notif is not None
    assert "sos_emp" in notif.message
    assert "דליפת מים" in notif.message


def test_sos_prefers_direct_manager_over_admin(client, db_session):
    from app.models.user import User
    from app.models.notification import Notification

    admin = User.query.filter_by(role="admin").first()
    mgr = User(username="sos_mgr", role="manager")
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    emp = User(username="sos_emp2", role="employee", manager_id=mgr.id)
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "sos_emp2", "password": "x"})
    client.post("/sos", data={"message": "בדיקה"})

    mgr_notif = Notification.query.filter_by(user_id=mgr.id).first()
    admin_notif = Notification.query.filter(
        Notification.user_id == admin.id, Notification.message.contains("sos_emp2")
    ).first()

    assert mgr_notif is not None
    assert admin_notif is None  # לא היה צריך לפנות לאדמין כי יש מנהל ישיר


def test_sos_returns_whatsapp_link_when_recipient_has_phone(client, db_session):
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    admin.phone = "0521112222"
    db_session.commit()

    emp = User(username="sos_emp3", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "sos_emp3", "password": "x"})
    r = client.post("/sos", data={"message": "בדיקה"})
    data = r.get_json()

    assert len(data["whatsapp_targets"]) == 1
    assert data["whatsapp_targets"][0]["name"] == "admin"
    assert "972521112222" in data["whatsapp_targets"][0]["link"]

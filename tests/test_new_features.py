"""בדיקות לתכונות: התראות, סינון מתקדם, תבניות משימות, ייצוא דוחות."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_notification_created_on_task_assignment(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from app.models.notification import Notification

    admin = _login_admin(client)
    emp = User(username="notifyemp", email="notifyemp@test.com", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/", data={
        "title": "משימה עם התראה", "description": "", "priority": "LOW",
        "assigned_to_id": str(emp.id), "recurrence": "NONE",
    })

    notif = Notification.query.filter_by(user_id=emp.id).first()
    assert notif is not None
    assert "משימה עם התראה" in notif.message


def test_mark_notification_read(client, db_session):
    from app.models.notification import Notification, notify

    admin = _login_admin(client)
    notify(admin.id, "בדיקה", link="/")
    n = Notification.query.filter_by(user_id=admin.id).first()
    assert n.is_read is False

    client.post(f"/notifications/{n.id}/read")
    db_session.refresh(n)
    assert n.is_read is True


def test_advanced_filter_by_assignee(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    other = User(username="assigneefilter", email="assigneefilter@test.com", role="employee")
    other.set_password("x")
    db_session.add(other)
    db_session.commit()

    db_session.add_all([
        Task(title="משימה עצמית לאדמין", user_id=admin.id, assigned_to_id=admin.id),
        Task(title="לעובד אחר", user_id=admin.id, assigned_to_id=other.id),
    ])
    db_session.commit()

    r = client.get(f"/?assignee={other.id}")
    body = r.get_data(as_text=True)
    assert "לעובד אחר" in body
    assert "משימה עצמית לאדמין" not in body


def test_task_template_prefills_creation_modal(client, db_session):
    from app.models.task_template import TaskTemplate

    admin = _login_admin(client)
    tpl = TaskTemplate(name="תבנית בדיקה", title="כותרת מהתבנית", priority="HIGH", recurrence="WEEKLY", created_by_id=admin.id)
    db_session.add(tpl)
    db_session.commit()

    r = client.get("/")
    body = r.get_data(as_text=True)
    assert "תבנית בדיקה" in body
    assert 'data-title="כותרת מהתבנית"' in body


def test_manager_cannot_delete_template_outside_department(client, db_session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task_template import TaskTemplate

    dept_a = Department(name="מחלקה א")
    dept_b = Department(name="מחלקה ב")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    mgr = User(username="tplmgr", email="tplmgr@test.com", role="manager", department_id=dept_a.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    tpl = TaskTemplate(name="שייך למחלקה ב", title="כותרת", department_id=dept_b.id)
    db_session.add(tpl)
    db_session.commit()

    client.post("/login", data={"username": "tplmgr", "password": "x"})
    client.post(f"/admin/templates/{tpl.id}/delete")

    assert TaskTemplate.query.get(tpl.id) is not None


def test_export_excel_returns_valid_file(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    db_session.add(Task(title="משימת ייצוא", user_id=admin.id, assigned_to_id=admin.id))
    db_session.commit()

    r = client.get("/export/excel")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(r.data) > 100


def test_export_pdf_returns_valid_file(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    db_session.add(Task(title="משימת ייצוא PDF", user_id=admin.id, assigned_to_id=admin.id))
    db_session.commit()

    r = client.get("/export/pdf")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf"
    assert r.data[:4] == b"%PDF"


def test_export_respects_filters(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    db_session.add_all([
        Task(title="גלוי", user_id=admin.id, assigned_to_id=admin.id, status="TODO"),
        Task(title="מוסתר", user_id=admin.id, assigned_to_id=admin.id, status="DONE"),
    ])
    db_session.commit()

    r = client.get("/export/excel?status=TODO")
    import openpyxl, io
    wb = openpyxl.load_workbook(io.BytesIO(r.data))
    ws = wb.active
    titles = [row[0] for row in ws.iter_rows(min_row=2, values_only=True)]
    assert "גלוי" in titles
    assert "מוסתר" not in titles

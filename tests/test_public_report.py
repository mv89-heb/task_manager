"""בדיקות לטופס דיווח תקלה ציבורי (ללא צורך בהתחברות)."""


def test_report_page_accessible_without_login(client):
    r = client.get("/report")
    assert r.status_code == 200


def test_report_creates_task(client, db_session):
    from app.models.task import Task

    client.post("/report", data={
        "title": "מעלית תקועה", "description": "בקומה 3", "department_id": "",
        "reporter_name": "", "reporter_phone": "",
    })

    task = Task.query.filter_by(title="מעלית תקועה").first()
    assert task is not None
    assert task.source == "public"
    assert task.status == "TODO"


def test_report_requires_title(client, db_session):
    from app.models.task import Task

    r = client.post("/report", data={"title": "", "description": "בלי כותרת"})
    body = r.get_data(as_text=True)
    assert "לתאר" in body
    assert Task.query.filter_by(description="בלי כותרת").first() is None


def test_report_stores_reporter_contact_info(client, db_session):
    from app.models.task import Task

    client.post("/report", data={
        "title": "ברז נוזל", "description": "", "reporter_name": "דנה כהן", "reporter_phone": "0501112233",
    })

    task = Task.query.filter_by(title="ברז נוזל").first()
    assert task.reporter_name == "דנה כהן"
    assert task.reporter_phone == "0501112233"


def test_report_honeypot_blocks_bots_silently(client, db_session):
    """אם שדה ה-honeypot הנסתר מלא (בוט), המשימה לא נוצרת בכלל אבל מוצגת הודעת הצלחה מטעה."""
    from app.models.task import Task

    r = client.post("/report", data={
        "title": "משימת בוט", "description": "", "website": "http://spam.example.com",
    })
    body = r.get_data(as_text=True) if r.status_code == 200 else ""
    assert Task.query.filter_by(title="משימת בוט").first() is None


def test_report_assigns_to_department_manager_when_exists(client, db_session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    dept = Department(name="מחלקת דיווח")
    db_session.add(dept)
    db_session.commit()

    mgr = User(username="reportmgr", role="manager", department_id=dept.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/report", data={"title": "תקלה במחלקה", "description": "", "department_id": str(dept.id)})

    task = Task.query.filter_by(title="תקלה במחלקה").first()
    assert task.assigned_to_id == mgr.id
    assert task.department_id == dept.id


def test_report_falls_back_to_admin_when_no_department_manager(client, db_session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    dept = Department(name="מחלקה בלי מנהל")
    db_session.add(dept)
    db_session.commit()

    admin = User.query.filter_by(role="admin").first()

    client.post("/report", data={"title": "תקלה ללא מנהל מחלקה", "description": "", "department_id": str(dept.id)})

    task = Task.query.filter_by(title="תקלה ללא מנהל מחלקה").first()
    assert task.assigned_to_id == admin.id


def test_report_notifies_department_manager(client, db_session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.notification import Notification

    dept = Department(name="מחלקת התראה")
    db_session.add(dept)
    db_session.commit()

    mgr = User(username="notifymgr", role="manager", department_id=dept.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/report", data={"title": "תקלה עם התראה", "description": "", "department_id": str(dept.id)})

    notif = Notification.query.filter_by(user_id=mgr.id).first()
    assert notif is not None
    assert "תקלה עם התראה" in notif.message


def test_public_reports_excluded_from_main_task_list(client, db_session):
    """דרישה מפורשת: לא לערבב דיווחים עם משימות - הרשימה הרגילה לא אמורה להראות אותם בכלל."""
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "משימה לתגית", "description": ""})

    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert "משימה לתגית" not in body


def test_reporter_contact_shown_in_edit_page(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "תקלה עם טלפון", "description": "", "reporter_name": "יוסי", "reporter_phone": "0509998888"})

    task = Task.query.filter_by(title="תקלה עם טלפון").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    r = client.get(f"/edit/{task.id}")
    body = r.get_data(as_text=True)
    assert "יוסי" in body
    assert "0509998888" in body


def test_reported_issues_tab_shows_only_public_reports(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "דיווח בלשונית", "description": ""})

    internal_task = Task(title="משימה פנימית נפרדת", user_id=admin.id, assigned_to_id=admin.id, source="internal")
    db_session.add(internal_task)
    db_session.commit()

    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    r = client.get("/reported_issues")
    body = r.get_data(as_text=True)
    assert "דיווח בלשונית" in body
    assert "משימה פנימית נפרדת" not in body


def test_reported_issues_tab_requires_admin_or_manager(client, db_session):
    from app.models.user import User

    emp = User(username="reportedissuesnoperm", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "reportedissuesnoperm", "password": "x"})
    r = client.get("/reported_issues", follow_redirects=True)
    assert "משימות" in r.get_data(as_text=True)  # הופנה חזרה, לא רואה את הלשונית


def test_reported_issues_tab_shows_public_report_link(client, db_session):
    admin_login = client.post("/login", data={"username": "admin", "password": "Admin@2026!"})
    r = client.get("/reported_issues")
    body = r.get_data(as_text=True)
    assert "/report" in body


def test_reported_issues_status_filter(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "דיווח פתוח", "description": ""})
    client.post("/report", data={"title": "דיווח סגור", "description": ""})

    closed = Task.query.filter_by(title="דיווח סגור").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    client.get(f"/done/{closed.id}")

    r = client.get("/reported_issues?status=DONE")
    body = r.get_data(as_text=True)
    assert "דיווח סגור" in body
    assert "דיווח פתוח" not in body


def test_pending_reports_count_in_nav_badge(client, db_session):
    from app.models.user import User

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "דיווח לתג ניווט", "description": ""})

    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "תקלות מדווחות" in body
    assert 'badge bg-danger rounded-pill me-2">1</span>' in body


def test_pending_reports_count_hidden_for_employee(client, db_session):
    from app.models.user import User

    emp = User(username="noreportsbadge", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "noreportsbadge", "password": "x"})
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert "תקלות מדווחות" not in body


def test_pending_reports_count_decreases_when_resolved(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = User.query.filter_by(role="admin").first()
    client.post("/report", data={"title": "דיווח לסגירה", "description": ""})

    task = Task.query.filter_by(title="דיווח לסגירה").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    client.get(f"/done/{task.id}")

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert 'badge bg-danger rounded-pill' not in body

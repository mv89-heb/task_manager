"""בדיקות לתיקון באג המחיקה: כפתור מחיקה בלשונית תקלות מדווחות + במסך עריכה,
והחזרה לעמוד הנכון (referrer) במקום תמיד לרשימה הרגילה."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_reported_issues_page_has_delete_button(client, db_session):
    admin = _login_admin(client)
    client.post("/report", data={"title": "תקלה למחיקה", "description": ""})

    r = client.get("/reported_issues")
    body = r.get_data(as_text=True)
    assert "/delete/" in body
    assert "bi-trash" in body


def test_edit_task_page_has_delete_button(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="משימה למחיקה מהעריכה", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    r = client.get(f"/edit/{task.id}")
    body = r.get_data(as_text=True)
    assert f"/delete/{task.id}" in body
    assert "מחק משימה זו" in body


def test_delete_public_report_actually_removes_it(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    client.post("/report", data={"title": "תקלה שתימחק בפועל", "description": ""})

    task = Task.query.filter_by(title="תקלה שתימחק בפועל").first()
    assert task is not None

    client.post(f"/delete/{task.id}")

    assert Task.query.filter_by(title="תקלה שתימחק בפועל").first() is None


def test_delete_redirects_back_to_reported_issues_when_called_from_there(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    client.post("/report", data={"title": "תקלה עם הפניה חזרה", "description": ""})
    task = Task.query.filter_by(title="תקלה עם הפניה חזרה").first()

    r = client.post(
        f"/delete/{task.id}",
        headers={"Referer": "http://localhost/reported_issues"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/reported_issues" in r.headers["Location"]


def test_delete_redirects_to_index_when_no_referrer(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="בלי referrer", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    r = client.post(f"/delete/{task.id}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["Location"].rstrip("/") == "http://localhost" or r.headers["Location"] == "/"


def test_delete_ignores_external_referrer(client, db_session):
    """הגנה: לא סומכים על referrer מאתר חיצוני - תמיד חוזרים לתוך האתר שלנו."""
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="הגנת referrer חיצוני", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    r = client.post(
        f"/delete/{task.id}",
        headers={"Referer": "https://evil.example.com/steal"},
        follow_redirects=False,
    )
    assert "evil.example.com" not in r.headers["Location"]


def test_employee_does_not_see_delete_button_on_edit_page(client, db_session):
    """עובד רגיל לא אמור להגיע בכלל למסך העריכה (רק admin/manager יכולים), אבל נוודא שהתנאי בתבנית תקין."""
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="בדיקת הרשאה לעריכה", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()
    task_id = task.id

    emp = User(username="editpermcheck", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.get("/logout")
    client.post("/login", data={"username": "editpermcheck", "password": "x"})
    r = client.get(f"/edit/{task_id}", follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "מחק משימה זו" not in body

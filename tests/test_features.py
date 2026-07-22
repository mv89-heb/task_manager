"""בדיקות פיצ'רים: משימות חוזרות, תגובות, תמונה מצורפת, דוח מחלקות."""
import io
import re


def _get_csrf(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else None


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_recurring_task_creates_next_occurrence_on_done(client, db_session):
    from app.models.task import Task
    from datetime import date

    admin = _login_admin(client)
    task = Task(title="ניקוי שבועי", user_id=admin.id, assigned_to_id=admin.id,
                recurrence="WEEKLY", due_date=date(2026, 7, 13), status="TODO")
    db_session.add(task)
    db_session.commit()

    client.get(f"/done/{task.id}")

    children = Task.query.filter_by(recurrence_parent_id=task.id).all()
    assert len(children) == 1
    assert children[0].due_date == date(2026, 7, 20)
    assert children[0].status == "TODO"


def test_non_recurring_task_does_not_duplicate(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="חד פעמית", user_id=admin.id, assigned_to_id=admin.id, recurrence="NONE")
    db_session.add(task)
    db_session.commit()

    client.get(f"/done/{task.id}")

    assert Task.query.filter_by(recurrence_parent_id=task.id).count() == 0


def test_add_comment_to_task(client, db_session):
    from app.models.task import Task
    from app.models.comment import TaskComment

    admin = _login_admin(client)
    task = Task(title="בדיקת תגובות", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    client.post(f"/task/{task.id}/comment", data={"body": "בודק שהתגובה נשמרת"})

    comments = TaskComment.query.filter_by(task_id=task.id).all()
    assert len(comments) == 1
    assert comments[0].body == "בודק שהתגובה נשמרת"
    assert comments[0].user_id == admin.id


def test_cannot_comment_on_task_outside_permission_scope(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from app.models.comment import TaskComment

    admin = _login_admin(client)
    other = User(username="other", email="other@test.com", role="employee")
    other.set_password("x")
    db_session.add(other)
    db_session.commit()

    task = Task(title="לא לי", user_id=admin.id, assigned_to_id=other.id)
    db_session.add(task)
    db_session.commit()

    client.get("/logout")
    client.post("/login", data={"username": "other", "password": "x"})
    # other IS the assignee, so should succeed - now test with a THIRD unrelated user
    client.get("/logout")

    third = User(username="third", email="third@test.com", role="employee")
    third.set_password("x")
    db_session.add(third)
    db_session.commit()
    client.post("/login", data={"username": "third", "password": "x"})

    client.post(f"/task/{task.id}/comment", data={"body": "לא אמור להישמר"})
    assert TaskComment.query.filter_by(task_id=task.id).count() == 0


def test_image_upload_rejects_oversized_file(client, db_session):
    from app.models.task import Task, MAX_IMAGE_SIZE_BYTES

    admin = _login_admin(client)
    task = Task(title="עם תמונה", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    oversized = io.BytesIO(b"x" * (MAX_IMAGE_SIZE_BYTES + 1))
    client.post(f"/edit/{task.id}", data={
        "title": "עם תמונה", "description": "", "priority": "LOW", "status": "TODO",
        "assigned_to_id": str(admin.id), "recurrence": "NONE",
        "image": (oversized, "big.jpg", "image/jpeg"),
    }, content_type="multipart/form-data")

    refreshed = Task.query.get(task.id)
    assert refreshed.image_data is None


def test_image_upload_accepts_valid_small_image(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    task = Task(title="עם תמונה 2", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(task)
    db_session.commit()

    small_image = io.BytesIO(b"\xff\xd8\xff" + b"fakejpegdata" * 10)
    client.post(f"/edit/{task.id}", data={
        "title": "עם תמונה 2", "description": "", "priority": "LOW", "status": "TODO",
        "assigned_to_id": str(admin.id), "recurrence": "NONE",
        "image": (small_image, "small.jpg", "image/jpeg"),
    }, content_type="multipart/form-data")

    refreshed = Task.query.get(task.id)
    assert refreshed.image_data is not None
    assert refreshed.image_mimetype == "image/jpeg"


def test_department_dashboard_stats(client, db_session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    admin = _login_admin(client)
    dept = Department(name="בדיקה")
    db_session.add(dept)
    db_session.commit()

    emp = User(username="deptemp", email="deptemp@test.com", role="employee", department_id=dept.id)
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    db_session.add_all([
        Task(title="t1", user_id=admin.id, assigned_to_id=emp.id, status="DONE"),
        Task(title="t2", user_id=admin.id, assigned_to_id=emp.id, status="TODO"),
    ])
    db_session.commit()

    r = client.get("/dashboard")
    body = r.get_data(as_text=True)
    assert "בדיקה" in body
    assert "50%" in body

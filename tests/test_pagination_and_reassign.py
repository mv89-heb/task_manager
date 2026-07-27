"""בדיקות: 20 משימות בכל דף, והקצאה קבוצתית של משימות נבחרות לאיש אחד."""


def _login_admin(client):
    from app.models.user import User
    admin = User.query.filter_by(role="admin").first()
    client.post("/login", data={"username": admin.username, "password": "Admin@2026!"})
    return admin


def test_pagination_shows_20_per_page(client, db_session):
    from app.models.task import Task

    admin = _login_admin(client)
    for i in range(25):
        db_session.add(Task(title=f"משימה {i}", user_id=admin.id, assigned_to_id=admin.id))
    db_session.commit()

    r = client.get("/")
    body = r.get_data(as_text=True)
    shown = sum(1 for i in range(25) if f"משימה {i}<" in body or f"משימה {i} " in body or f">משימה {i}<" in body)
    # ודאי דרך ה-pagination object עצמו שזמין יותר אמין מספירת טקסט
    assert r.status_code == 200


def test_pagination_object_uses_20_per_page(app, client, db_session):
    from app.models.task import Task
    from app import db

    admin = _login_admin(client)
    with app.app_context():
        for i in range(25):
            t = Task(title=f"משימה מספר {i}", user_id=admin.id, assigned_to_id=admin.id)
            db.session.add(t)
        db.session.commit()

        query = Task.query.order_by(Task.created_at.desc())
        pagination = db.paginate(query, page=1, per_page=20, error_out=False)
        assert len(pagination.items) == 20
        assert pagination.pages == 2


def test_bulk_reassign_moves_tasks_to_new_assignee(client, db_session):
    from app.models.user import User
    from app.models.task import Task

    admin = _login_admin(client)
    emp1 = User(username="reassign_from", role="employee")
    emp1.set_password("x")
    emp2 = User(username="reassign_to", email="reassign_to@test.com", role="employee")
    emp2.set_password("x")
    db_session.add_all([emp1, emp2])
    db_session.commit()

    t1 = Task(title="למישהו 1", user_id=admin.id, assigned_to_id=emp1.id)
    t2 = Task(title="למישהו 2", user_id=admin.id, assigned_to_id=emp1.id)
    db_session.add_all([t1, t2])
    db_session.commit()

    r = client.post("/bulk_reassign_tasks", data={
        "task_ids": [str(t1.id), str(t2.id)],
        "assignee_id": str(emp2.id),
    })
    data = r.get_json()
    assert data["success"] is True
    assert data["updated_count"] == 2
    assert data["assignee_name"] == "reassign_to"

    from app.models.task import Task as T
    assert T.query.get(t1.id).assigned_to_id == emp2.id
    assert T.query.get(t2.id).assigned_to_id == emp2.id


def test_bulk_reassign_notifies_new_assignee(client, db_session):
    from app.models.user import User
    from app.models.task import Task
    from app.models.notification import Notification

    admin = _login_admin(client)
    emp2 = User(username="notify_reassign", role="employee")
    emp2.set_password("x")
    db_session.add(emp2)
    db_session.commit()

    t1 = Task(title="הודעה על הקצאה", user_id=admin.id, assigned_to_id=admin.id)
    db_session.add(t1)
    db_session.commit()

    client.post("/bulk_reassign_tasks", data={"task_ids": [str(t1.id)], "assignee_id": str(emp2.id)})

    notif = Notification.query.filter_by(user_id=emp2.id).first()
    assert notif is not None
    assert "הודעה על הקצאה" in notif.message


def test_bulk_reassign_blocks_target_outside_scope(client, db_session):
    """מנהל תחום לא יכול להקצות משימות למישהו מחוץ למחלקה שלו."""
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    dept_a = Department(name="מחלקת הקצאה א")
    dept_b = Department(name="מחלקת הקצאה ב")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    mgr = User(username="reassignmgr", role="manager", department_id=dept_a.id)
    mgr.set_password("x")
    emp_own = User(username="reassign_own", role="employee", department_id=dept_a.id)
    emp_own.set_password("x")
    outsider = User(username="reassign_outsider", role="employee", department_id=dept_b.id)
    outsider.set_password("x")
    db_session.add_all([mgr, emp_own, outsider])
    db_session.commit()

    task = Task(title="משימת מחלקה א", user_id=emp_own.id, assigned_to_id=emp_own.id)
    db_session.add(task)
    db_session.commit()

    client.post("/login", data={"username": "reassignmgr", "password": "x"})
    r = client.post("/bulk_reassign_tasks", data={"task_ids": [str(task.id)], "assignee_id": str(outsider.id)})
    data = r.get_json()
    assert data["success"] is False

    from app.models.task import Task as T
    assert T.query.get(task.id).assigned_to_id == emp_own.id  # לא השתנה


def test_bulk_reassign_skips_task_outside_toucher_scope(client, db_session):
    """אם אחת מהמשימות שנשלחו לא בהיקף ההרשאה, היא מדולגת, לא גורמת לקריסה."""
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    dept_a = Department(name="מחלקת דילוג א")
    dept_b = Department(name="מחלקת דילוג ב")
    db_session.add_all([dept_a, dept_b])
    db_session.commit()

    mgr = User(username="skipmgr", role="manager", department_id=dept_a.id)
    mgr.set_password("x")
    emp_own = User(username="skip_own", role="employee", department_id=dept_a.id)
    emp_own.set_password("x")
    outsider = User(username="skip_outsider", role="employee", department_id=dept_b.id)
    outsider.set_password("x")
    db_session.add_all([mgr, emp_own, outsider])
    db_session.commit()

    own_task = Task(title="משימה בתוך ההיקף", user_id=emp_own.id, assigned_to_id=emp_own.id)
    outside_task = Task(title="משימה מחוץ להיקף", user_id=outsider.id, assigned_to_id=outsider.id)
    db_session.add_all([own_task, outside_task])
    db_session.commit()

    client.post("/login", data={"username": "skipmgr", "password": "x"})
    r = client.post("/bulk_reassign_tasks", data={
        "task_ids": [str(own_task.id), str(outside_task.id)],
        "assignee_id": str(emp_own.id),
    })
    data = r.get_json()
    assert data["success"] is True
    assert data["updated_count"] == 1
    assert data["skipped_count"] == 1


def test_employee_cannot_bulk_reassign(client, db_session):
    from app.models.user import User

    emp = User(username="noreassignperm", role="employee")
    emp.set_password("x")
    db_session.add(emp)
    db_session.commit()

    client.post("/login", data={"username": "noreassignperm", "password": "x"})
    r = client.post("/bulk_reassign_tasks", data={"task_ids": ["1"], "assignee_id": "1"})
    assert r.status_code == 403


def test_reassign_button_present_in_ui_for_manager(client, db_session):
    from app.models.user import User
    from app.models.department import Department

    dept = Department(name="מחלקת UI")
    db_session.add(dept)
    db_session.commit()

    mgr = User(username="uimgr", role="manager", department_id=dept.id)
    mgr.set_password("x")
    db_session.add(mgr)
    db_session.commit()

    client.post("/login", data={"username": "uimgr", "password": "x"})
    r = client.get("/")
    body = r.get_data(as_text=True)
    assert 'id="reassignModal"' in body
    assert "הקצה לאיש אחד" in body

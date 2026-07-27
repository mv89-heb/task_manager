"""בדיקות היקף ההרשאות ההיררכיות: admin / manager / employee, עם/בלי מחלקה."""
import pytest


def _make_org(session):
    from app.models.user import User
    from app.models.department import Department
    from app.models.task import Task

    dept = Department(name="אחזקה")
    session.add(dept)
    session.commit()

    admin = User.query.filter_by(role="admin").first()  # נוצר אוטומטית ב-create_app

    mgr = User(username="mgr", email="mgr@test.com", role="manager", department_id=dept.id)
    mgr.set_password("x")
    emp = User(username="emp", email="emp@test.com", role="employee", department_id=dept.id)
    emp.set_password("x")
    outsider = User(username="outsider", email="outsider@test.com", role="employee")  # ללא מחלקה
    outsider.set_password("x")
    session.add_all([mgr, emp, outsider])
    session.commit()

    t_in_dept = Task(title="in-dept", user_id=admin.id, assigned_to_id=emp.id)
    t_outsider = Task(title="outsider-task", user_id=admin.id, assigned_to_id=outsider.id)
    session.add_all([t_in_dept, t_outsider])
    session.commit()

    return {"admin": admin, "mgr": mgr, "emp": emp, "outsider": outsider,
            "t_in_dept": t_in_dept, "t_outsider": t_outsider}


def test_admin_sees_everyone(app, db_session):
    org = _make_org(db_session)
    assert set(u.id for u in org["admin"].visible_users_query().all()) >= {
        org["mgr"].id, org["emp"].id, org["outsider"].id
    }


def test_manager_sees_only_own_department(app, db_session):
    org = _make_org(db_session)
    visible_ids = set(org["mgr"].visible_user_ids())
    assert org["emp"].id in visible_ids
    assert org["outsider"].id not in visible_ids


def test_employee_sees_only_self(app, db_session):
    org = _make_org(db_session)
    assert org["emp"].visible_user_ids() == [org["emp"].id]


def test_manager_cannot_touch_task_outside_department(app, db_session):
    from app.routes.tasks import can_touch_task
    org = _make_org(db_session)
    assert can_touch_task(org["mgr"], org["t_in_dept"]) is True
    assert can_touch_task(org["mgr"], org["t_outsider"]) is False


def test_employee_cannot_touch_others_task(app, db_session):
    from app.routes.tasks import can_touch_task
    org = _make_org(db_session)
    assert can_touch_task(org["emp"], org["t_in_dept"]) is True
    assert can_touch_task(org["emp"], org["t_outsider"]) is False


def test_manager_cannot_reassign_task_outside_department(client, db_session):
    org = _make_org(db_session)
    client.post("/login", data={"username": "mgr", "password": "x"})
    client.post(f"/edit/{org['t_in_dept'].id}", data={
        "title": "in-dept", "description": "", "priority": "LOW", "status": "TODO",
        "assigned_to_id": str(org["outsider"].id),
    })
    from app.models.task import Task
    refreshed = Task.query.get(org["t_in_dept"].id)
    assert refreshed.assigned_to_id != org["outsider"].id

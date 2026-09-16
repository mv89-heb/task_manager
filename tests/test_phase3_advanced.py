import pytest
from app import db
from app.models.task import Task, TaskChecklistItem
from app.models.user import User

def get_or_create_admin(app):
    """פונקציית עזר ליצירת משתמש מנהל לבדיקות"""
    with app.app_context():
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(username="admin_test", email="admin@test.com", role="admin")
            admin.set_password("pass123")
            db.session.add(admin)
            db.session.commit()
        else:
            admin.set_password("pass123")
            db.session.commit()
        return admin

def test_timeline_route(client, app):
    """בדיקת גישה תקינה לעמוד ציר הזמן (Timeline)"""
    admin = get_or_create_admin(app)
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    response = client.get('/timeline')
    assert response.status_code == 200
    assert b'Timeline' in response.data or 'ציר זמן'.encode('utf-8') in response.data

def test_checklist_api_add_and_toggle(client, app):
    """בדיקת הוספה וסימון של פריטי רשימת תיוג דרך ה-API (AJAX)"""
    admin = get_or_create_admin(app)
    with app.app_context():
        task = Task(title="Test Task Checklist", assigned_to_id=admin.id)
        db.session.add(task)
        db.session.commit()
        task_id = task.id
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    add_resp = client.post(f'/task/{task_id}/checklist', json={'text': 'My Checklist Item'})
    assert add_resp.status_code == 200
    add_data = add_resp.get_json()
    assert add_data['success'] is True
    assert add_data['text'] == 'My Checklist Item'
    item_id = add_data['item_id']
    toggle_resp = client.post(f'/checklist/{item_id}/toggle', json={})
    assert toggle_resp.status_code == 200
    toggle_data = toggle_resp.get_json()
    assert toggle_data['success'] is True
    assert toggle_data['is_done'] is True

def test_task_dependencies_soft_block(client, app):
    """בדיקת מנגנון החסימה הרכה (Soft Block) בסיום משימה עם תלויות פתוחות"""
    admin = get_or_create_admin(app)
    with app.app_context():
        task_dependency = Task(title="Blocking Task", status="TODO", assigned_to_id=admin.id)
        task_main = Task(title="Main Task", status="TODO", assigned_to_id=admin.id)
        db.session.add_all([task_dependency, task_main])
        db.session.commit()
        task_main.dependencies.append(task_dependency)
        db.session.commit()
        task_main_id = task_main.id
    client.post('/login', data={"username": admin.username, "password": "pass123"})
    resp_warning = client.post(f'/update_status/{task_main_id}', json={'status': 'DONE'})
    assert resp_warning.status_code == 200
    data_warning = resp_warning.get_json()
    assert data_warning.get('warning') is True
    assert "תלויות שטרם הושלמו" in data_warning['message']
    resp_force = client.post(f'/update_status/{task_main_id}', json={'status': 'DONE', 'force_complete': True})
    assert resp_force.status_code == 200
    data_force = resp_force.get_json()
    assert data_force.get('success') is True

def test_sub_tasks_association(app):
    """בדיקת תקינות הקשר העצמי (Self-Referential) של תתי-משימות במסד הנתונים"""
    admin = get_or_create_admin(app)
    with app.app_context():
        parent_task = Task(title="Parent Task", assigned_to_id=admin.id)
        db.session.add(parent_task)
        db.session.commit()
        child_task = Task(title="Child Task", parent_task_id=parent_task.id, assigned_to_id=admin.id)
        db.session.add(child_task)
        db.session.commit()
        p = db.session.get(Task, parent_task.id)
        assert p.sub_tasks.count() == 1
        assert p.sub_tasks.first().title == "Child Task"
        assert p.sub_tasks.first().parent_task.id == parent_task.id

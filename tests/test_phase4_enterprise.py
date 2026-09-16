import pytest
from datetime import datetime, timedelta, date
from app import db
from app.models.task import Task
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE
from app.models.sla import SlaPolicy
from app.models.department import Department
from app.services import sla_service, workload_service
import json

def test_sla_policy_assignment(app):
    """בדיקת מנוע ה-SLA."""
    with app.app_context():
        policy_critical = SlaPolicy(name='Critical Bug', priority='CRITICAL', max_hours=2.0)
        policy_high = SlaPolicy(name='High Priority', priority='HIGH', max_hours=8.0)
        db.session.add_all([policy_critical, policy_high])
        db.session.commit()
        task_critical = Task(title="Server Down", priority="CRITICAL")
        db.session.add(task_critical)
        db.session.flush()
        sla_service.assign_sla(task_critical)
        assert task_critical.sla_breach_at is not None
        diff = task_critical.sla_breach_at - task_critical.created_at
        assert diff.total_seconds() == 7200

def test_workload_calculation(app):
    """בדיקת מנוע העומסים."""
    with app.app_context():
        manager = User(username="manager_test", role=ROLE_ADMIN)
        manager.set_password("manager-test-123")
        employee = User(username="employee_test", role=ROLE_EMPLOYEE)
        employee.set_password("employee-test-123")
        db.session.add_all([manager, employee])
        db.session.commit()
        task1 = Task(title="T1", estimated_minutes=120, assigned_to_id=employee.id, status="TODO")
        task2 = Task(title="T2", estimated_minutes=120, assigned_to_id=employee.id, status="IN_PROGRESS")
        task3 = Task(title="T3", estimated_minutes=60, assigned_to_id=employee.id, status="TODO", due_date=date.today() - timedelta(days=2))
        db.session.add_all([task1, task2, task3])
        db.session.commit()
        workload = workload_service.get_team_workload(manager)
        employee_data = next((w for w in workload if w['user'].id == employee.id), None)
        assert employee_data is not None
        assert employee_data['task_count'] == 3
        assert employee_data['total_hours'] == 5.0
        assert employee_data['overdue_count'] == 1
        assert employee_data['status_color'] in ['warning', 'danger']

def test_global_search_api(client, app):
    """בדיקת ה-API של החיפוש הגלובלי."""
    with app.app_context():
        admin = User(username="search_admin", role=ROLE_ADMIN)
        admin.set_password("Pass123!")
        dept = Department(name="Finance Search")
        task = Task(title="Audit Finance Report 2026", description="Important")
        db.session.add_all([admin, dept, task])
        db.session.commit()
    client.post('/login', data={'username': 'search_admin', 'password': 'Pass123!'})
    response = client.get('/api/search?q=Finance')
    assert response.status_code == 200
    data = response.get_json()
    assert "tasks" in data and "users" in data and "departments" in data
    task_titles = [t['title'] for t in data['tasks']]
    dept_names = [d['name'] for d in data['departments']]
    assert "Audit Finance Report 2026" in task_titles
    assert "Finance Search" in dept_names

def test_visual_workflow_builder_api(client, app):
    """בדיקת הארכיטקטורה של Workflow Builder."""
    with app.app_context():
        admin = User(username="workflow_admin", role=ROLE_ADMIN)
        admin.set_password("Pass123!")
        db.session.add(admin)
        db.session.commit()
    client.post('/login', data={'username': 'workflow_admin', 'password': 'Pass123!'})
    payload = {
        "name": "SLA Breach Action",
        "trigger_event": "task_overdue",
        "department_id": None,
        "conditions": [
            {"field": "priority", "operator": "equals", "value": "HIGH"},
            {"field": "status", "operator": "not_equals", "value": "DONE"}
        ],
        "actions": [
            {"type": "change_priority", "params": {"priority": "HIGH"}},
            {"type": "notify_all_admins", "params": {}}
        ]
    }
    response = client.post('/admin/automations', data=json.dumps(payload), content_type='application/json')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    with app.app_context():
        from app.models.automation import AutomationRule
        rule = AutomationRule.query.filter_by(name="SLA Breach Action").first()
        assert rule is not None
        assert len(rule.conditions) == 2
        assert len(rule.actions) == 2
        assert rule.actions[0]['type'] == 'change_priority'

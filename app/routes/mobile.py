from datetime import date

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db, csrf
from app.models.task import Task
from app.routes.tasks import bp


def _visible_tasks_query():
    """Return tasks using the exact same visibility rules as the main web UI."""
    from app.routes.tasks import visible_task_query
    return visible_task_query(current_user).filter(Task.source != "public")


def _task_payload(task):
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "status": task.status,
        "priority": task.priority or "LOW",
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "assignee": task.assignee.username if task.assignee else None,
        "department": task.department.name if task.department else None,
        "is_overdue": bool(task.due_date and task.due_date < date.today() and task.status != "DONE"),
        "can_edit": current_user.role == "admin"
        or (current_user.role == "manager" and task.assigned_to_id in current_user.visible_user_ids())
        or (current_user.role == "employee" and task.assigned_to_id == current_user.id),
    }


@bp.route("/mobile")
def mobile_home():
    return render_template("mobile/index.html")


@bp.route("/api/mobile/me")
def mobile_me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False}), 401
    return jsonify({
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role,
            "role_label": current_user.role_label(),
            "department": current_user.department.name if current_user.department else None,
            "must_change_password": bool(current_user.must_change_password),
        },
    })


@bp.route("/api/mobile/tasks")
@login_required
def mobile_tasks():
    query = _visible_tasks_query()

    status = request.args.get("status", "").strip()
    if status in {"TODO", "IN_PROGRESS", "DONE"}:
        query = query.filter(Task.status == status)

    search = request.args.get("search", "").strip()
    if search:
        query = query.filter(
            or_(Task.title.ilike(f"%{search}%"), Task.description.ilike(f"%{search}%"))
        )

    sort = request.args.get("sort", "due_date")
    if sort == "created":
        query = query.order_by(Task.created_at.desc())
    elif sort == "priority":
        priority_order = db.case(
            (Task.priority == "CRITICAL", 0),
            (Task.priority == "HIGH", 1),
            (Task.priority == "MEDIUM", 2),
            else_=3,
        )
        query = query.order_by(priority_order, Task.due_date.asc().nullslast())
    else:
        query = query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())

    limit = min(max(request.args.get("limit", 100, type=int), 1), 200)
    tasks = query.limit(limit).all()

    counts_query = _visible_tasks_query()
    counts = {
        "todo": counts_query.filter(Task.status == "TODO").count(),
        "in_progress": counts_query.filter(Task.status == "IN_PROGRESS").count(),
        "done": counts_query.filter(Task.status == "DONE").count(),
        "overdue": counts_query.filter(
            Task.status != "DONE", Task.due_date.isnot(None), Task.due_date < date.today()
        ).count(),
    }

    return jsonify({
        "tasks": [_task_payload(task) for task in tasks],
        "counts": counts,
    })


@bp.route("/api/mobile/tasks/<int:task_id>")
@login_required
def mobile_task(task_id):
    task = db.session.get(Task, task_id)
    if not task or task.source == "public":
        return jsonify({"error": "Task not found"}), 404
    visible = _visible_tasks_query().filter(Task.id == task_id).first()
    if not visible:
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"task": _task_payload(task)})


@bp.route("/api/mobile/tasks/<int:task_id>/status", methods=["POST"])
@csrf.exempt
@login_required
def mobile_update_status(task_id):
    task = db.session.get(Task, task_id)
    if not task or task.source == "public":
        return jsonify({"error": "Task not found"}), 404

    from app.routes.tasks import can_touch_task, _create_next_recurrence

    if not can_touch_task(current_user, task):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in {"TODO", "IN_PROGRESS", "DONE"}:
        return jsonify({"error": "Invalid status"}), 400

    previous_status = task.status
    task.status = status
    db.session.commit()

    next_task = None
    if previous_status != "DONE" and status == "DONE" and task.recurrence and task.recurrence != "NONE":
        next_task = _create_next_recurrence(task)

    return jsonify({
        "success": True,
        "task": _task_payload(task),
        "next_task_id": next_task.id if next_task else None,
    })

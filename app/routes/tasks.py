from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app.models.task import Task
from app import db
from datetime import datetime

bp = Blueprint("tasks", __name__)

@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None

        task = Task(
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            due_date=due_date,
            priority=request.form.get("priority", "LOW"),
        )
        db.session.add(task)
        db.session.commit()
        flash("המשימה נוצרה בהצלחה!", "success")
        return redirect("/")

    search_query = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    query = Task.query

    if search_query:
        query = query.filter((Task.title.contains(search_query)) | (Task.description.contains(search_query)))
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    if sort_by == "due_date":
        query = query.order_by(Task.due_date.asc() if order == "asc" else Task.due_date.desc())
    elif sort_by == "priority":
        query = query.order_by(Task.priority.asc() if order == "asc" else Task.priority.desc())
    else:
        query = query.order_by(Task.created_at.asc() if order == "asc" else Task.created_at.desc())

    pagination = db.paginate(query, page=page, per_page=5, error_out=False)
    tasks = pagination.items

    return render_template("tasks.html", tasks=tasks, pagination=pagination, sort_by=sort_by, order=order)

@bp.route("/done/<int:id>")
def done(id):
    task = Task.query.get(id)
    if task:
        task.status = "DONE"
        db.session.commit()
        flash("כל הכבוד! המשימה בוצעה 🎉", "confetti")
    return redirect("/")

@bp.route("/delete/<int:id>")
def delete(id):
    task = Task.query.get(id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash("המשימה נמחקה בהצלחה.", "danger")
    return redirect("/")

@bp.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    task = Task.query.get(id)
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
        
        task.title = request.form.get("title", "")
        task.description = request.form.get("description", "")
        task.priority = request.form.get("priority", "LOW")
        
        db.session.commit()
        flash("השינויים נשמרו.", "success")
        return redirect("/")
    return render_template("edit_task.html", task=task)

# --- תצוגת קאנבן ---
@bp.route("/kanban")
def kanban():
    tasks = Task.query.all()
    # חלוקה מראש ל-3 עמודות על בסיס שדה ה-status
    todo = [t for t in tasks if t.status == "TODO" or not t.status]
    in_progress = [t for t in tasks if t.status == "IN_PROGRESS"]
    done = [t for t in tasks if t.status == "DONE"]
    
    return render_template("kanban.html", todo=todo, in_progress=in_progress, done=done)

# --- עדכון סטטוס שקט בעקבות גרירה בקאנבן (AJAX) ---
@bp.route("/update_status/<int:id>", methods=["POST"])
def update_status(id):
    task = Task.query.get(id)
    if task:
        data = request.get_json()
        new_status = data.get("status")
        
        if new_status in ["TODO", "IN_PROGRESS", "DONE"]:
            task.status = new_status
            db.session.commit()
            return jsonify({"success": True})
            
    return jsonify({"success": False}), 400

# --- תצוגת לוח שנה ---
@bp.route("/calendar")
def calendar():
    return render_template("calendar.html")

# --- API עבור לוח השנה ---
@bp.route("/api/calendar_tasks")
def calendar_tasks():
    tasks = Task.query.filter(Task.due_date.isnot(None)).all()
    events = []
    for t in tasks:
        if t.status == "DONE":
            color = "#22c55e"
        elif t.priority == "HIGH":
            color = "#ef4444"
        elif t.priority == "MEDIUM":
            color = "#f59e0b"
        else:
            color = "#3b82f6"

        events.append({
            "id": t.id,
            "title": t.title,
            "start": t.due_date.isoformat(),
            "backgroundColor": color,
            "borderColor": color,
            "url": f"/edit/{t.id}"
        })
    return jsonify(events)

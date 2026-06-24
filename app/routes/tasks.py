from flask import Blueprint, render_template, request, redirect, url_for
from app.models.task import Task
from app import db
from datetime import datetime

bp = Blueprint("tasks", __name__)

@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # קליטת התאריך (אם הושאר ריק, נשמור כ-None)
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
        return redirect("/")

    # נציג את המשימות (אפשר למיין אותן לפי תאריך יצירה)
    tasks = Task.query.order_by(Task.created_at.desc()).all()
    return render_template("tasks.html", tasks=tasks)

@bp.route("/done/<int:id>")
def done(id):
    task = Task.query.get(id)
    if task:
        task.status = "DONE"
        db.session.commit()
    return redirect("/")

@bp.route("/delete/<int:id>")
def delete(id):
    task = Task.query.get(id)
    if task:
        db.session.delete(task)
        db.session.commit()
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
        return redirect("/")

    return render_template("edit_task.html", task=task)

from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        flash("המשימה נוצרה בהצלחה!", "success") # הודעה ירוקה
        return redirect("/")

    search_query = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    query = Task.query
    if search_query:
        query = query.filter((Task.title.contains(search_query)) | (Task.description.contains(search_query)))
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    tasks = query.order_by(Task.created_at.desc()).all()
    return render_template("tasks.html", tasks=tasks)

@bp.route("/done/<int:id>")
def done(id):
    task = Task.query.get(id)
    if task:
        task.status = "DONE"
        db.session.commit()
        flash("כל הכבוד! המשימה בוצעה 🎉", "confetti") # הודעת קונפטי מיוחדת!
    return redirect("/")

@bp.route("/delete/<int:id>")
def delete(id):
    task = Task.query.get(id)
    if task:
        db.session.delete(task)
        db.session.commit()
        flash("המשימה נמחקה בהצלחה.", "danger") # הודעה אדומה
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
        flash("השינויים נשמרו עודכנו.", "success")
        return redirect("/")

    return render_template("edit_task.html", task=task)

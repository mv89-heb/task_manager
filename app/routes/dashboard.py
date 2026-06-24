from flask import Blueprint, render_template
from app.models.task import Task
from datetime import date

bp = Blueprint("dashboard", __name__)

@bp.route("/dashboard")
def dashboard():
    tasks = Task.query.all()
    today = date.today()

    # חישוב סטטוסים כלליים
    total = len(tasks)
    done_tasks = [t for t in tasks if t.status == "DONE"]
    open_tasks = [t for t in tasks if t.status != "DONE"]
    
    done_count = len(done_tasks)
    open_count = len(open_tasks)

    # נתונים חכמים רק למשימות פתוחות
    high_priority = len([t for t in open_tasks if t.priority == "HIGH"])
    medium_priority = len([t for t in open_tasks if t.priority == "MEDIUM"])
    low_priority = len([t for t in open_tasks if t.priority == "LOW"])
    
    # חישוב איחורים (יש תאריך יעד והוא קטן מהיום)
    overdue = len([t for t in open_tasks if t.due_date and t.due_date < today])

    return render_template(
        "dashboard.html",
        total=total,
        done=done_count,
        open_count=open_count,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority,
        overdue=overdue
    )

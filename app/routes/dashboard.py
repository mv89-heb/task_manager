from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.task import Task
from datetime import date

bp = Blueprint("dashboard", __name__)

@bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    # שליחת נתונים מסוננים לפי המשתמש הנוכחי בלבד
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    total = len(tasks)
    done_tasks = [t for t in tasks if t.status == "DONE"]
    open_tasks = [t for t in tasks if t.status != "DONE"]
    
    done_count = len(done_tasks)
    open_count = len(open_tasks)
    
    completion_percent = int((done_count / total * 100)) if total > 0 else 0

    high_priority = len([t for t in open_tasks if t.priority == "HIGH"])
    medium_priority = len([t for t in open_tasks if t.priority == "MEDIUM"])
    low_priority = len([t for t in open_tasks if t.priority == "LOW"])
    
    overdue_tasks = [t for t in open_tasks if t.due_date and t.due_date < today]
    today_tasks = [t for t in open_tasks if t.due_date == today]
    
    urgent_list = [t for t in open_tasks if (t.due_date and t.due_date < today) or t.priority == "HIGH"]
    urgent_list = sorted(urgent_list, key=lambda x: x.due_date or date.max)[:5]

    return render_template(
        "dashboard.html",
        total=total,
        done=done_count,
        open_count=open_count,
        completion_percent=completion_percent,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority,
        overdue_count=len(overdue_tasks),
        today_tasks=today_tasks,
        urgent_list=urgent_list
    )

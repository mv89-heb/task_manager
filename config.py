from flask import Blueprint, render_template
from app.models.task import Task

bp = Blueprint("dashboard", __name__)

@bp.route("/dashboard")
def dashboard():
    tasks = Task.query.all()
    return render_template(
        "dashboard.html",
        total=len(tasks),
        done=len([t for t in tasks if t.status=="DONE"])
    )

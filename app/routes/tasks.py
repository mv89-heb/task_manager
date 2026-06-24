from flask import Blueprint, render_template, request, redirect, url_for
from app.models.task import Task
from app import db

bp = Blueprint("tasks", __name__)

# LIST + CREATE
@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        task = Task(
            title=request.form["title"],
            priority=request.form["priority"],
        )
        db.session.add(task)
        db.session.commit()
        return redirect("/")

    tasks = Task.query.all()
    return render_template("tasks.html", tasks=tasks)

# MARK DONE
@bp.route("/done/<int:id>")
def done(id):
    task = Task.query.get(id)
    task.status = "DONE"
    db.session.commit()
    return redirect("/")

# DELETE
@bp.route("/delete/<int:id>")
def delete(id):
    task = Task.query.get(id)
    db.session.delete(task)
    db.session.commit()
    return redirect("/")

# EDIT PAGE
@bp.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    task = Task.query.get(id)

    if request.method == "POST":
        task.title = request.form["title"]
        task.priority = request.form["priority"]
        db.session.commit()
        return redirect("/")

    return render_template("edit_task.html", task=task)
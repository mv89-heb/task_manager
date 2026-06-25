from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.task import Task
from app.models.user import User
from app import db
from datetime import date

bp = Blueprint("dashboard", __name__)

@bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    total = len(tasks)
    done_count = len([t for t in tasks if t.status == "DONE"])
    open_count = len([t for t in tasks if t.status != "DONE"])
    completion_percent = int((done_count / total * 100)) if total > 0 else 0

    high_priority = len([t for t in tasks if t.status != "DONE" and t.priority == "HIGH"])
    medium_priority = len([t for t in tasks if t.status != "DONE" and t.priority == "MEDIUM"])
    low_priority = len([t for t in tasks if t.status != "DONE" and t.priority == "LOW"])
    
    today_tasks = [t for t in tasks if t.status != "DONE" and t.due_date == today]
    urgent_list = [t for t in tasks if t.status != "DONE" and (t.priority == "HIGH" or (t.due_date and t.due_date < today))]
    urgent_list = sorted(urgent_list, key=lambda x: x.due_date or date.max)[:5]

    return render_template(
        "dashboard.html", total=total, done=done_count, open_count=open_count,
        completion_percent=completion_percent, high_priority=high_priority,
        medium_priority=medium_priority, low_priority=low_priority,
        overdue_count=len([t for t in tasks if t.status != "DONE" and t.due_date and t.due_date < today]),
        today_tasks=today_tasks, urgent_list=urgent_list
    )

# =========================================================
# 👑 פאנל ניהול (מערכת ניהול משתמשים מקיפה)
# =========================================================

@bp.route("/admin")
@login_required
def admin_panel():
    if current_user.role != 'manager':
        flash("אין לך הרשאות לגשת לעמוד זה.", "danger")
        return redirect(url_for('tasks.index'))
        
    all_users = User.query.order_by(User.id.desc()).all()
    user_stats = []
    for u in all_users:
        task_count = Task.query.filter_by(assigned_to_id=u.id).count()
        user_stats.append({'user': u, 'task_count': task_count})
        
    return render_template("admin.html", user_stats=user_stats)

@bp.route("/admin/user/new", methods=["GET", "POST"])
@login_required
def admin_add_user():
    if current_user.role != 'manager':
        return redirect(url_for('tasks.index'))

    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        role = request.form.get("role", "employee") # קליטת התפקיד מהטופס

        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("שם המשתמש או האימייל כבר קיימים.", "danger")
            return redirect(url_for("dashboard.admin_add_user"))

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f"המשתמש {username} נוצר בהצלחה בתפקיד {role}!", "success")
        return redirect(url_for("dashboard.admin_panel"))

    return render_template("admin_user_form.html", user=None)

@bp.route("/admin/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_user(user_id):
    if current_user.role != 'manager':
        return redirect(url_for('tasks.index'))

    user_to_edit = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_username = request.form.get("username").strip()
        
        if user_to_edit.username == 'mv' and new_username != 'mv':
            flash("אי אפשר לשנות את שם המשתמש של המנהל הראשי (mv).", "danger")
            return redirect(url_for("dashboard.admin_edit_user", user_id=user_id))

        user_to_edit.username = new_username
        user_to_edit.email = request.form.get("email").strip()
        user_to_edit.role = request.form.get("role", "employee") # עדכון התפקיד מהטופס
        
        new_password = request.form.get("password")
        if new_password:
            user_to_edit.set_password(new_password)

        try:
            db.session.commit()
            flash("פרטי המשתמש והרשאותיו עודכנו בהצלחה.", "success")
            return redirect(url_for("dashboard.admin_panel"))
        except:
            db.session.rollback()
            flash("שגיאה בעדכון: הפרטים כבר תפוסים.", "danger")

    return render_template("admin_user_form.html", user=user_to_edit)

@bp.route("/admin/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if current_user.role != 'manager':
        return redirect(url_for('tasks.index'))
        
    user_to_delete = User.query.get_or_404(user_id)
    if user_to_delete.username == 'mv':
        flash("אי אפשר למחוק את חשבון המנהל הראשי!", "danger")
        return redirect(url_for('dashboard.admin_panel'))
        
    Task.query.filter_by(assigned_to_id=user_to_delete.id).delete()
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f"המשתמש '{user_to_delete.username}' נמחק לצמיתות.", "success")
    return redirect(url_for('dashboard.admin_panel'))

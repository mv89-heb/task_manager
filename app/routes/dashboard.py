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


# =========================================================
# 👑 פאנל ניהול (מערכת ניהול משתמשים מקיפה)
# =========================================================

# --- הצגת רשימת המשתמשים ---
@bp.route("/admin")
@login_required
def admin_panel():
    if current_user.username != 'mv':
        flash("אין לך הרשאות לגשת לעמוד זה.", "danger")
        return redirect(url_for('tasks.index'))
        
    all_users = User.query.order_by(User.id.desc()).all()
    user_stats = []
    for u in all_users:
        task_count = Task.query.filter_by(user_id=u.id).count()
        user_stats.append({
            'user': u,
            'task_count': task_count
        })
        
    return render_template("admin.html", user_stats=user_stats)

# --- הוספת משתמש חדש דרך הפאנל ---
@bp.route("/admin/user/new", methods=["GET", "POST"])
@login_required
def admin_add_user():
    if current_user.username != 'mv':
        return redirect(url_for('tasks.index'))

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("שם המשתמש או האימייל כבר קיימים במערכת.", "danger")
            return redirect(url_for("dashboard.admin_add_user"))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash(f"המשתמש {username} נוצר בהצלחה!", "success")
        return redirect(url_for("dashboard.admin_panel"))

    return render_template("admin_user_form.html", user=None)

# --- עריכת משתמש קיים ---
@bp.route("/admin/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_user(user_id):
    if current_user.username != 'mv':
        return redirect(url_for('tasks.index'))

    user_to_edit = User.query.get_or_404(user_id)

    if request.method == "POST":
        new_username = request.form.get("username")
        
        # הגנה: מניעת שינוי שם המשתמש של המנהל (כדי לא לאבד גישה לפאנל)
        if user_to_edit.username == 'mv' and new_username != 'mv':
            flash("אזהרת אבטחה: אי אפשר לשנות את שם המשתמש של המנהל הראשי (mv).", "danger")
            return redirect(url_for("dashboard.admin_edit_user", user_id=user_id))

        user_to_edit.username = new_username
        user_to_edit.email = request.form.get("email")
        new_password = request.form.get("password")

        # מעדכן סיסמה רק אם המנהל הזין אחת חדשה
        if new_password:
            user_to_edit.set_password(new_password)

        try:
            db.session.commit()
            flash("פרטי המשתמש עודכנו בהצלחה.", "success")
            return redirect(url_for("dashboard.admin_panel"))
        except:
            db.session.rollback()
            flash("שגיאה בעדכון: ייתכן שהאימייל או השם כבר תפוסים.", "danger")

    return render_template("admin_user_form.html", user=user_to_edit)

# --- מחיקת משתמש ---
@bp.route("/admin/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    if current_user.username != 'mv':
        return redirect(url_for('tasks.index'))
        
    user_to_delete = User.query.get_or_404(user_id)
    
    if user_to_delete.id == current_user.id:
        flash("אי אפשר למחוק את חשבון המנהל הראשי שלך דרך הפאנל!", "danger")
        return redirect(url_for('dashboard.admin_panel'))
        
    Task.query.filter_by(user_id=user_to_delete.id).delete()
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f"המשתמש '{user_to_delete.username}' נמחק לצמיתות.", "success")
    return redirect(url_for('dashboard.admin_panel'))

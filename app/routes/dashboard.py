from flask import Blueprint, render_template, redirect, url_for, flash
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

# =========================================================
# 👑 פאנל ניהול סודי למנהלים בלבד
# =========================================================

@bp.route("/admin")
@login_required
def admin_panel():
    # חומת אבטחה: רק משתמש בשם 'mv' יכול לגשת
    if current_user.username != 'mv':
        flash("אין לך הרשאות לגשת לעמוד זה.", "danger")
        return redirect(url_for('tasks.index'))
        
    all_users = User.query.all()
    # אסיפת כמות המשימות לכל משתמש כדי להציג בטבלה
    user_stats = []
    for u in all_users:
        task_count = Task.query.filter_by(user_id=u.id).count()
        user_stats.append({
            'user': u,
            'task_count': task_count
        })
        
    return render_template("admin.html", user_stats=user_stats)


@bp.route("/admin/delete_user/<int:user_id>")
@login_required
def delete_user(user_id):
    # חומת אבטחה 
    if current_user.username != 'mv':
        flash("אין לך הרשאות לבצע פעולה זו.", "danger")
        return redirect(url_for('tasks.index'))
        
    user_to_delete = User.query.get_or_404(user_id)
    
    # חסימה: לא מאפשרים למנהל למחוק את עצמו בטעות
    if user_to_delete.id == current_user.id:
        flash("אי אפשר למחוק את חשבון המנהל הראשי שלך דרך הפאנל!", "danger")
        return redirect(url_for('dashboard.admin_panel'))
        
    # מחיקת כל המשימות של המשתמש לפני מחיקת המשתמש עצמו
    Task.query.filter_by(user_id=user_to_delete.id).delete()
    
    # מחיקת המשתמש ממסד הנתונים
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash(f"המשתמש '{user_to_delete.username}' וכל המשימות שלו נמחקו לצמיתות.", "success")
    return redirect(url_for('dashboard.admin_panel'))

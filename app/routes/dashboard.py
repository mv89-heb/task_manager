from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models.task import Task
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE, ROLE_LABELS
from app.models.department import Department
from app.models.task_template import TaskTemplate
from app import db
from datetime import date

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    # היקף הנתונים בדשבורד תלוי בתפקיד: מנהל מערכת רואה הכל, מנהל תחום רואה
    # את המחלקה שלו, ועובד רואה רק את המשימות שהוקצו לו.
    if current_user.role == ROLE_ADMIN:
        tasks = Task.query.all()
    elif current_user.role == ROLE_MANAGER:
        tasks = Task.query.filter(Task.assigned_to_id.in_(current_user.visible_user_ids())).all()
    else:
        tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()

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

    # פירוט ביצועים לפי מחלקה - רלוונטי רק למנהל מערכת (תמונה ארגונית מלאה)
    department_stats = []
    unassigned_dept_count = 0
    if current_user.role == ROLE_ADMIN:
        all_users_by_dept = {}
        for u in User.query.all():
            all_users_by_dept.setdefault(u.department_id, []).append(u.id)

        for dept in Department.query.order_by(Department.name).all():
            member_ids = all_users_by_dept.get(dept.id, [])
            dept_tasks = [t for t in tasks if t.assigned_to_id in member_ids]
            dept_total = len(dept_tasks)
            dept_done = len([t for t in dept_tasks if t.status == "DONE"])
            department_stats.append({
                'name': dept.name,
                'member_count': len(member_ids),
                'total': dept_total,
                'done': dept_done,
                'open': dept_total - dept_done,
                'completion_percent': int((dept_done / dept_total * 100)) if dept_total > 0 else 0,
            })

        # משתמשים (וכפועל יוצא, המשימות שלהם) שעדיין לא שויכו לאף מחלקה
        unassigned_ids = all_users_by_dept.get(None, [])
        unassigned_dept_count = len([t for t in tasks if t.assigned_to_id in unassigned_ids])

    return render_template(
        "dashboard.html", total=total, done=done_count, open_count=open_count,
        completion_percent=completion_percent, high_priority=high_priority,
        medium_priority=medium_priority, low_priority=low_priority,
        overdue_count=len([t for t in tasks if t.status != "DONE" and t.due_date and t.due_date < today]),
        today_tasks=today_tasks, urgent_list=urgent_list,
        department_stats=department_stats, unassigned_dept_count=unassigned_dept_count
    )


# =========================================================
# 👑 פאנל ניהול (ניהול משתמשים לפי היררכיה: admin / manager / employee)
# =========================================================

@bp.route("/admin")
@login_required
def admin_panel():
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        flash("אין לך הרשאות לגשת לעמוד זה.", "danger")
        return redirect(url_for('tasks.index'))

    # מנהל מערכת רואה את כולם; מנהל תחום רואה רק את חברי המחלקה שלו
    visible_users = current_user.visible_users_query().order_by(User.id.desc()).all()

    user_stats = []
    for u in visible_users:
        task_count = Task.query.filter_by(assigned_to_id=u.id).count()
        user_stats.append({'user': u, 'task_count': task_count})

    departments = Department.query.order_by(Department.name).all() if current_user.role == ROLE_ADMIN else []

    return render_template(
        "admin.html",
        user_stats=user_stats,
        departments=departments,
        role_labels=ROLE_LABELS,
    )


@bp.route("/admin/user/new", methods=["GET", "POST"])
@login_required
def admin_add_user():
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        return redirect(url_for('tasks.index'))

    departments = Department.query.order_by(Department.name).all()
    # מנהל תחום יכול ליצור עובדים רק במחלקה שלו; מנהל מערכת רואה את כל המחלקות
    assignable_departments = departments if current_user.role == ROLE_ADMIN else [
        d for d in departments if d.id == current_user.department_id
    ]
    possible_managers = User.query.filter(User.role.in_([ROLE_ADMIN, ROLE_MANAGER])).all()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip() or None
        phone = request.form.get("phone", "").strip() or None
        password = request.form.get("password")
        role = request.form.get("role", ROLE_EMPLOYEE)
        department_id = request.form.get("department_id") or None
        manager_id = request.form.get("manager_id") or None

        if not current_user.can_assign_role(role):
            flash("אינך רשאי להעניק תפקיד זה.", "danger")
            return redirect(url_for("dashboard.admin_add_user"))

        # מנהל תחום מוגבל תמיד למחלקה שלו, ולא יכול לבחור מחלקה אחרת
        if current_user.role == ROLE_MANAGER:
            department_id = current_user.department_id

        if User.query.filter_by(username=username).first() or (email and User.query.filter_by(email=email).first()):
            flash("שם המשתמש או האימייל כבר קיימים.", "danger")
            return redirect(url_for("dashboard.admin_add_user"))

        new_user = User(
            username=username,
            email=email,
            phone=phone,
            role=role,
            department_id=int(department_id) if department_id else None,
            manager_id=int(manager_id) if manager_id else None,
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash(f"המשתמש {username} נוצר בהצלחה בתפקיד {ROLE_LABELS.get(role, role)}!", "success")
        return redirect(url_for("dashboard.admin_panel"))

    return render_template(
        "admin_user_form.html",
        user=None,
        departments=assignable_departments,
        possible_managers=possible_managers,
        role_labels=ROLE_LABELS,
    )


@bp.route("/admin/user/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_user(user_id):
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        return redirect(url_for('tasks.index'))

    user_to_edit = User.query.get_or_404(user_id)

    if not current_user.can_manage_user(user_to_edit):
        flash("אינך רשאי לערוך משתמש זה.", "danger")
        return redirect(url_for('dashboard.admin_panel'))

    departments = Department.query.order_by(Department.name).all()
    assignable_departments = departments if current_user.role == ROLE_ADMIN else [
        d for d in departments if d.id == current_user.department_id
    ]
    possible_managers = User.query.filter(User.role.in_([ROLE_ADMIN, ROLE_MANAGER])).all()

    if request.method == "POST":
        new_username = request.form.get("username", "").strip()

        if user_to_edit.username == 'mv' and new_username != 'mv':
            flash("אי אפשר לשנות את שם המשתמש של המנהל הראשי (mv).", "danger")
            return redirect(url_for("dashboard.admin_edit_user", user_id=user_id))

        role = request.form.get("role", user_to_edit.role)
        if not current_user.can_assign_role(role):
            flash("אינך רשאי להעניק תפקיד זה.", "danger")
            return redirect(url_for("dashboard.admin_edit_user", user_id=user_id))

        if user_to_edit.role == ROLE_ADMIN and role != ROLE_ADMIN and User.query.filter_by(role=ROLE_ADMIN).count() <= 1:
            flash("אי אפשר להוריד בדרגה את מנהל המערכת האחרון שנשאר - חייב להישאר לפחות admin אחד.", "danger")
            return redirect(url_for("dashboard.admin_edit_user", user_id=user_id))

        department_id = request.form.get("department_id") or None
        manager_id = request.form.get("manager_id") or None

        if current_user.role == ROLE_MANAGER:
            # מנהל תחום לא יכול להעביר עובד למחלקה אחרת
            department_id = current_user.department_id

        user_to_edit.username = new_username
        user_to_edit.email = request.form.get("email", "").strip() or None
        user_to_edit.phone = request.form.get("phone", "").strip() or None
        user_to_edit.role = role
        user_to_edit.department_id = int(department_id) if department_id else None
        user_to_edit.manager_id = int(manager_id) if manager_id else None

        new_password = request.form.get("password")
        if new_password:
            user_to_edit.set_password(new_password)

        try:
            db.session.commit()
            flash("פרטי המשתמש והרשאותיו עודכנו בהצלחה.", "success")
            return redirect(url_for("dashboard.admin_panel"))
        except Exception:
            db.session.rollback()
            flash("שגיאה בעדכון: הפרטים כבר תפוסים.", "danger")

    return render_template(
        "admin_user_form.html",
        user=user_to_edit,
        departments=assignable_departments,
        possible_managers=possible_managers,
        role_labels=ROLE_LABELS,
    )


@bp.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@login_required
def delete_user(user_id):
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        return redirect(url_for('tasks.index'))

    user_to_delete = User.query.get_or_404(user_id)

    if user_to_delete.username == 'mv':
        flash("אי אפשר למחוק את חשבון המנהל הראשי!", "danger")
        return redirect(url_for('dashboard.admin_panel'))

    if user_to_delete.role == ROLE_ADMIN and User.query.filter_by(role=ROLE_ADMIN).count() <= 1:
        flash("אי אפשר למחוק את מנהל המערכת האחרון שנשאר - חייב להישאר לפחות admin אחד.", "danger")
        return redirect(url_for('dashboard.admin_panel'))

    if not current_user.can_manage_user(user_to_delete):
        flash("אינך רשאי למחוק משתמש זה.", "danger")
        return redirect(url_for('dashboard.admin_panel'))

    Task.query.filter_by(assigned_to_id=user_to_delete.id).delete()
    db.session.delete(user_to_delete)
    db.session.commit()

    flash(f"המשתמש '{user_to_delete.username}' נמחק לצמיתות.", "success")
    return redirect(url_for('dashboard.admin_panel'))


# =========================================================
# 🏢 ניהול מחלקות (רק למנהל מערכת)
# =========================================================

@bp.route("/admin/departments", methods=["GET", "POST"])
@login_required
def admin_departments():
    if current_user.role != ROLE_ADMIN:
        flash("רק מנהל מערכת יכול לנהל מחלקות.", "danger")
        return redirect(url_for('tasks.index'))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("יש להזין שם מחלקה.", "danger")
        elif Department.query.filter_by(name=name).first():
            flash("מחלקה בשם זה כבר קיימת.", "danger")
        else:
            db.session.add(Department(name=name, description=description))
            db.session.commit()
            flash(f"המחלקה '{name}' נוצרה בהצלחה.", "success")
        return redirect(url_for("dashboard.admin_departments"))

    departments = Department.query.order_by(Department.name).all()
    dept_stats = []
    for d in departments:
        member_count = User.query.filter_by(department_id=d.id).count()
        manager_names = [u.username for u in d.members if u.role == ROLE_MANAGER]
        dept_stats.append({'dept': d, 'member_count': member_count, 'managers': manager_names})

    return render_template("admin_departments.html", dept_stats=dept_stats)


@bp.route("/admin/departments/<int:dept_id>/delete", methods=["POST"])
@login_required
def delete_department(dept_id):
    if current_user.role != ROLE_ADMIN:
        return redirect(url_for('tasks.index'))

    dept = Department.query.get_or_404(dept_id)
    if User.query.filter_by(department_id=dept.id).count() > 0:
        flash("לא ניתן למחוק מחלקה שיש בה משתמשים. יש להעביר אותם למחלקה אחרת קודם.", "danger")
    else:
        db.session.delete(dept)
        db.session.commit()
        flash(f"המחלקה '{dept.name}' נמחקה.", "success")
    return redirect(url_for("dashboard.admin_departments"))


# =========================================================
# 📐 תבניות משימות (זמינות למנהל מערכת ולמנהלי תחום)
# =========================================================

@bp.route("/admin/templates", methods=["GET", "POST"])
@login_required
def admin_templates():
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        flash("אין לך הרשאה לנהל תבניות.", "danger")
        return redirect(url_for('tasks.index'))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        title = request.form.get("title", "").strip()
        if not name or not title:
            flash("יש למלא שם תבנית וכותרת משימה.", "danger")
        else:
            template = TaskTemplate(
                name=name,
                title=title,
                description=request.form.get("description", "").strip(),
                priority=request.form.get("priority", "LOW"),
                recurrence=request.form.get("recurrence", "NONE"),
                department_id=current_user.department_id if current_user.role == ROLE_MANAGER else (int(request.form.get("department_id")) if request.form.get("department_id") else None),
                created_by_id=current_user.id,
            )
            db.session.add(template)
            db.session.commit()
            flash(f"התבנית '{name}' נוצרה בהצלחה.", "success")
        return redirect(url_for("dashboard.admin_templates"))

    if current_user.role == ROLE_ADMIN:
        templates = TaskTemplate.query.order_by(TaskTemplate.name).all()
    else:
        templates = TaskTemplate.query.filter(
            (TaskTemplate.department_id == current_user.department_id) | (TaskTemplate.department_id.is_(None))
        ).order_by(TaskTemplate.name).all()

    departments = Department.query.order_by(Department.name).all()
    return render_template("admin_templates.html", templates=templates, departments=departments)


@bp.route("/admin/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def delete_template(template_id):
    if current_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        return redirect(url_for('tasks.index'))

    template = TaskTemplate.query.get_or_404(template_id)
    if current_user.role == ROLE_MANAGER and template.department_id != current_user.department_id:
        flash("אינך רשאי למחוק תבנית זו.", "danger")
        return redirect(url_for("dashboard.admin_templates"))

    db.session.delete(template)
    db.session.commit()
    flash(f"התבנית '{template.name}' נמחקה.", "success")
    return redirect(url_for("dashboard.admin_templates"))


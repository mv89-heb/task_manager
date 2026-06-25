from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models.task import Task
from app.models.user import User
from app import db, mail
from flask_mail import Message
from datetime import datetime, date
from sqlalchemy import text

bp = Blueprint("tasks", __name__)

# =========================================================
# 🔒 מערכת ניהול משתמשים (Authentication)
# =========================================================

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.index"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f"ברוך הבא, {user.username}!", "success")
            return redirect(url_for("tasks.index"))
        else:
            flash("איมייל או סיסמה לא נכונים.", "danger")
    return render_template("login.html")

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.index"))
    if request.method == "POST":
        username = request.form.get("username").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("שם המשתמש או האימייל כבר קיימים.", "danger")
            return redirect(url_for("tasks.register"))
        try:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash("החשבון נוצר בהצלחה! 🎉", "success")
            return redirect(url_for("tasks.index"))
        except Exception as e:
            db.session.rollback()
            flash(f"שגיאה ברישום: {e}", "danger")
            return redirect(url_for("tasks.register"))
    return render_template("register.html")

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("התנתקת בהצלחה.", "success")
    return redirect(url_for("tasks.login"))


# =========================================================
# 📋 ניהול משימות והרשאות (Core Task & Roles)
# =========================================================

@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    # שליפת כל המשתמשים עבור טופס ההקצאה של המנהל
    all_users = User.query.all() if current_user.role == 'manager' else []

    if request.method == "POST":
        if current_user.role != 'manager':
            flash("רק מנהלים מורשים ליצור משימות חדשות.", "danger")
            return redirect(url_for("tasks.index"))

        due_date_str = request.form.get("due_date")
        due_date = None
        if due_date_str:
            try:
                parsed_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                if parsed_date.year <= 9999:
                    due_date = parsed_date
            except ValueError:
                pass

        assigned_to_id = request.form.get("assigned_to_id")
        if not assigned_to_id:
            assigned_to_id = current_user.id

        task = Task(
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            due_date=due_date,
            priority=request.form.get("priority", "LOW"),
            user_id=current_user.id,
            assigned_to_id=assigned_to_id
        )
        db.session.add(task)
        db.session.commit()
        flash("המשימה נוצרה והוקצתה בהצלחה!", "success")
        return redirect(url_for("tasks.index"))

    # לוגיקת סינון: מנהל רואה את הכל, עובד רואה רק מה ששויך אליו
    if current_user.role == 'manager':
        query = Task.query
    else:
        query = Task.query.filter_by(assigned_to_id=current_user.id)

    # סינון לפי חיפוש חופשי
    search_query = request.args.get("search", "")
    if search_query:
        query = query.filter((Task.title.contains(search_query)) | (Task.description.contains(search_query)))

    # סינון לפי סטטוס
    status_filter = request.args.get("status", "")
    if status_filter:
        query = query.filter(Task.status == status_filter)
        
    # סינון לפי עדיפות
    priority_filter = request.args.get("priority", "")
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    # מיון ועימוד
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "created_at")
    
    if sort_by == "due_date":
        query = query.order_by(Task.due_date.asc())
    else:
        query = query.order_by(Task.created_at.desc())

    pagination = db.paginate(query, page=page, per_page=5, error_out=False)
    
    # מיפוי נכון של תאריך היום ל-HTML (now_date) למניעת קריסת שרת
    return render_template(
        "tasks.html", 
        tasks=pagination.items, 
        pagination=pagination, 
        sort_by=sort_by, 
        all_users=all_users, 
        now_date=date.today()
    )

@bp.route("/done/<int:id>")
@login_required
def done(id):
    if current_user.role == 'manager':
        task = Task.query.get_or_404(id)
    else:
        task = Task.query.filter_by(id=id, assigned_to_id=current_user.id).first_or_404()
        
    task.status = "DONE"
    db.session.commit()
    flash("כל הכבוד! המשימה בוצעה 🎉", "success")
    return redirect(url_for("tasks.index"))

@bp.route("/delete/<int:id>")
@login_required
def delete(id):
    if current_user.role != 'manager':
        flash("אין לך הרשאה למחוק משימות.", "danger")
        return redirect(url_for("tasks.index"))
        
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    flash("המשימה נמחקה בהצלחה.", "danger")
    return redirect(url_for("tasks.index"))

@bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    if current_user.role != 'manager':
        flash("אין לך הרשאה לערוך משימות. צפייה בלבד.", "danger")
        return redirect(url_for("tasks.index"))
        
    task = Task.query.get_or_404(id)
    if request.method == "POST":
        task.title = request.form.get("title", "")
        task.description = request.form.get("description", "")
        task.priority = request.form.get("priority", "LOW")
        
        due_date_str = request.form.get("due_date")
        if due_date_str:
            try:
                task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            task.due_date = None

        db.session.commit()
        flash("השינויים נשמרו המשימה עודכנה.", "success")
        return redirect(url_for("tasks.index"))
    return render_template("edit_task.html", task=task)


# =========================================================
# 🚀 תצוגות מתקדמות (Kanban & Calendar)
# =========================================================

@bp.route("/kanban")
@login_required
def kanban():
    if current_user.role == 'manager':
        tasks = Task.query.all()
    else:
        tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()
        
    todo = [t for t in tasks if t.status == "TODO" or not t.status]
    in_progress = [t for t in tasks if t.status == "IN_PROGRESS"]
    done = [t for t in tasks if t.status == "DONE"]
    return render_template("kanban.html", todo=todo, in_progress=in_progress, done=done)

@bp.route("/update_status/<int:id>", methods=["POST"])
@login_required
def update_status(id):
    if current_user.role == 'manager':
        task = Task.query.get(id)
    else:
        task = Task.query.filter_by(id=id, assigned_to_id=current_user.id).first()
        
    if task:
        data = request.get_json()
        new_status = data.get("status")
        if new_status in ["TODO", "IN_PROGRESS", "DONE"]:
            task.status = new_status
            db.session.commit()
            return jsonify({"success": True})
    return jsonify({"success": False}), 400

@bp.route("/calendar")
@login_required
def calendar():
    return render_template("calendar.html")

@bp.route("/api/calendar_tasks")
@login_required
def calendar_tasks():
    if current_user.role == 'manager':
        tasks = Task.query.filter(Task.due_date.isnot(None)).all()
    else:
        tasks = Task.query.filter_by(assigned_to_id=current_user.id).filter(Task.due_date.isnot(None)).all()
        
    events = []
    for t in tasks:
        color = "#22c55e" if t.status == "DONE" else ("#ef4444" if t.priority == "HIGH" else "#3b82f6")
        events.append({ 
            "id": t.id, 
            "title": t.title, 
            "start": t.due_date.isoformat(), 
            "backgroundColor": color, 
            "borderColor": color, 
            "url": f"/edit/{t.id}" if current_user.role == 'manager' else "#" 
        })
    return jsonify(events)


# =========================================================
# ✉️ מערכת איפוס סיסמה במייל
# =========================================================

def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for('tasks.reset_token', token=token, _external=True)
    msg = Message('איפוס סיסמה', sender='noreply@demo.com', recipients=[user.email])
    msg.body = f"לאיפוס לחץ על הקישור: {reset_url}"
    mail.send(msg)

@bp.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email")).first()
        if user: 
            send_reset_email(user)
        flash("אם האימייל קיים במערכת, נשלחו אליו הוראות לאיפוס הסיסמה.", "info")
        return redirect(url_for('tasks.login'))
    return render_template("reset_request.html")

@bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    user = User.verify_reset_token(token)
    if not user:
        flash("קישור פג תוקף או שגוי.", "danger")
        return redirect(url_for('tasks.reset_request'))
    if request.method == "POST":
        user.set_password(request.form.get("password"))
        db.session.commit()
        flash("הסיסמה שונתה בהצלחה.", "success")
        return redirect(url_for('tasks.login'))
    return render_template("reset_token.html")


# =========================================================
# 🛠️ כלי חילוץ ושדרוג אוטומטי למסד הנתונים
# =========================================================

@bp.route("/fix-db")
def fix_db():
    output = []
    try:
        db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN role VARCHAR(20) DEFAULT 'employee';"))
        db.session.commit()
        output.append("✅ עמודת 'role' נוספה לטבלת המשתמשים.")
    except Exception:
        db.session.rollback()
        output.append("ℹ️ עמודת 'role' כבר קיימת.")

    try:
        db.session.execute(text('ALTER TABLE task ADD COLUMN assigned_to_id INTEGER;'))
        db.session.commit()
        output.append("✅ עמודת 'assigned_to_id' נוספה לטבלת המשימות.")
        db.session.execute(text('UPDATE task SET assigned_to_id = user_id WHERE assigned_to_id IS NULL;'))
        db.session.commit()
    except Exception:
        db.session.rollback()
        output.append("ℹ️ עמודת 'assigned_to_id' כבר קיימת.")

    try:
        db.session.execute(text("UPDATE \"user\" SET role = 'manager' WHERE username = 'mv';"))
        db.session.commit()
        output.append("👑 המשתמש 'mv' הוגדר בהצלחה כמנהל המערכת.")
    except Exception:
        db.session.rollback()

    return "<br>".join(output) + "<br><br><b>השדרוג למערכת ארגונית הסתיים! חזור לאתר והתחבר.</b>"

@bp.route("/rescue")
def rescue():
    try:
        db.create_all()
        admin = User.query.filter_by(username='mv').first()
        if admin:
            admin.set_password("123456")
            db.session.commit()
            return f"✅ הסיסמה אופסה ל-123456 עבור {admin.email}"
        else:
            admin = User(username='mv', email='admin@test.com')
            admin.set_password("123456")
            db.session.add(admin)
            db.session.commit()
            return "✅ יוזר מנהל mv נוצר עם הסיסמה 123456"
    except Exception as e:
        db.session.rollback()
        return f"❌ שגיאה: {e}"

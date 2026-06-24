from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models.task import Task
from app.models.user import User
from app import db
from datetime import datetime
from sqlalchemy import text

bp = Blueprint("tasks", __name__)

# =========================================================
# 🔒 מערכת ניהול משתמשים (Authentication)
# =========================================================

# --- עמוד התחברות ---
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.index"))
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f"ברוך הבא, {user.username}!", "success")
            return redirect(url_for("tasks.index"))
        else:
            flash("אימייל או סיסמה לא נכונים.", "danger")
            
    return render_template("login.html")

# --- עמוד הרשמה ---
@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.index"))
        
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        
        if User.query.filter_by(email=email).first():
            flash("כתובת האימייל כבר קיימת במערכת.", "danger")
            return redirect(url_for("tasks.register"))
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash("נרשמת בהצלחה! כעת ניתן להתחבר.", "success")
        return redirect(url_for("tasks.login"))
        
    return render_template("register.html")

# --- התנתקות ---
@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("התנתקת מהמערכת בהצלחה.", "success")
    return redirect(url_for("tasks.login"))


# =========================================================
# 📋 ניהול משימות (Core Task Management)
# =========================================================

# --- עמוד הבית (רשימת משימות + סינון + מיון + עימוד) ---
@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None

        task = Task(
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            due_date=due_date,
            priority=request.form.get("priority", "LOW"),
            user_id=current_user.id  # שיוך המשימה למשתמש המחובר
        )
        db.session.add(task)
        db.session.commit()
        flash("המשימה נוצרה בהצלחה!", "success")
        return redirect(url_for("tasks.index"))

    # קליטת פרמטרים מכתובת ה-URL עבור חיפושים וסינונים
    search_query = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    # שליפת משימות השייכות אך ורק למשתמש המחובר
    query = Task.query.filter_by(user_id=current_user.id)

    # החלת סינונים במידה ונבחרו
    if search_query:
        query = query.filter((Task.title.contains(search_query)) | (Task.description.contains(search_query)))
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    # לוגיקת מיון דינמי
    if sort_by == "due_date":
        query = query.order_by(Task.due_date.asc() if order == "asc" else Task.due_date.desc())
    elif sort_by == "priority":
        query = query.order_by(Task.priority.asc() if order == "asc" else Task.priority.desc())
    else:
        query = query.order_by(Task.created_at.asc() if order == "asc" else Task.created_at.desc())

    # חלוקה לעמודים (Pagination) - 5 משימות לעמוד
    pagination = db.paginate(query, page=page, per_page=5, error_out=False)
    tasks = pagination.items

    return render_template("tasks.html", tasks=tasks, pagination=pagination, sort_by=sort_by, order=order)

# --- סימון משימה כבוצע ---
@bp.route("/done/<int:id>")
@login_required
def done(id):
    # מוודאים שהמשימה קיימת ושייכת למשתמש הנוכחי
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    task.status = "DONE"
    db.session.commit()
    flash("כל הכבוד! המשימה בוצעה 🎉", "confetti")
    return redirect(url_for("tasks.index"))

# --- מחיקת משימה ---
@bp.route("/delete/<int:id>")
@login_required
def delete(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    flash("המשימה נמחקה בהצלחה.", "danger")
    return redirect(url_for("tasks.index"))

# --- עריכת משימה קיימת ---
@bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None
        
        task.title = request.form.get("title", "")
        task.description = request.form.get("description", "")
        task.priority = request.form.get("priority", "LOW")
        
        db.session.commit()
        flash("השינויים נשמרו.", "success")
        return redirect(url_for("tasks.index"))
        
    return render_template("edit_task.html", task=task)


# =========================================================
# 🚀 תצוגות מתקדמות (Kanban & Calendar)
# =========================================================

# --- תצוגת לוח קאנבן ---
@bp.route("/kanban")
@login_required
def kanban():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    
    # מיון המשימות הפרטיות ל-3 עמודות הלוח
    todo = [t for t in tasks if t.status == "TODO" or not t.status]
    in_progress = [t for t in tasks if t.status == "IN_PROGRESS"]
    done = [t for t in tasks if t.status == "DONE"]
    
    return render_template("kanban.html", todo=todo, in_progress=in_progress, done=done)

# --- עדכון סטטוס שקט בעקבות גרירה בקאנבן (AJAX API) ---
@bp.route("/update_status/<int:id>", methods=["POST"])
@login_required
def update_status(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first()
    if task:
        data = request.get_json()
        new_status = data.get("status")
        
        if new_status in ["TODO", "IN_PROGRESS", "DONE"]:
            task.status = new_status
            db.session.commit()
            return jsonify({"success": True})
            
    return jsonify({"success": False}), 400

# --- תצוגת לוח שנה ---
@bp.route("/calendar")
@login_required
def calendar():
    return render_template("calendar.html")

# --- נקודת קצה (API) שמזינה את המשימות ללוח השנה בפורמט JSON ---
@bp.route("/api/calendar_tasks")
@login_required
def calendar_tasks():
    # שולפים רק משימות בעלות תאריך יעד ששייכות למשתמש הנוכחי
    tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.due_date.isnot(None)).all()
    events = []
    
    for t in tasks:
        # התאמת צבעים לפי סטטוס ועדיפות
        if t.status == "DONE":
            color = "#22c55e" # ירוק
        elif t.priority == "HIGH":
            color = "#ef4444" # אדום
        elif t.priority == "MEDIUM":
            color = "#f59e0b" # צהוב
        else:
            color = "#3b82f6" # כחול

        events.append({
            "id": t.id,
            "title": t.title,
            "start": t.due_date.isoformat(),
            "backgroundColor": color,
            "borderColor": color,
            "url": f"/edit/{t.id}"
        })
        
    return jsonify(events)


# =========================================================
# 🛠️ כלי תחזוקה וסנכרון (Database Fix Patch)
# =========================================================

# --- ראוט סודי להזרקת עמודת המשתמש למסד הנתונים הקיים ללא מחיקה ---
@bp.route("/fix-db")
def fix_db():
    try:
        # פקודה ידנית שמוסיפה את העמודה user_id לטבלה הקיימת ב-PostgreSQL
        db.session.execute(text('ALTER TABLE task ADD COLUMN user_id INTEGER;'))
        db.session.commit()
        return "✅ מסד הנתונים תוקן בהצלחה! העמודה user_id נוספה לטבלת המשימות שלך. ניתן לחזור לאתר."
    except Exception as e:
        return f"נראה שהעמודה כבר קיימת שם, או שיש שגיאה אחרת: {e}"

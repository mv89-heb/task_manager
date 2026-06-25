from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.models.task import Task
from app.models.user import User
from app import db, mail
from flask_mail import Message
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
            login_user(user, remember=True) # זוכר את המשתמש מחובר
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
        username = request.form.get("username").strip()
        email = request.form.get("email").strip()
        password = request.form.get("password")
        
        if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
            flash("שם המשתמש או כתובת האימייל כבר קיימים במערכת.", "danger")
            return redirect(url_for("tasks.register"))
            
        try:
            user = User(username=username, email=email)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # התחברות אוטומטית מיד לאחר ההרשמה
            login_user(user, remember=True)
            
            flash("החשבון שלך נוצר בהצלחה וברוך הבא לאפליקציה! 🎉", "success")
            return redirect(url_for("tasks.index"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"שגיאה ברישום המשתמש: {e}", "danger")
            return redirect(url_for("tasks.register"))
        
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

# --- עמוד הבית (רשימת משימות + יצירה + סינון) ---
@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        due_date = None
        
        if due_date_str:
            try:
                parsed_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                # הגנה חיונית: פייתון קורס בשנים שגדולות מ-9999 (כמו 62026)
                if parsed_date.year <= 9999:
                    due_date = parsed_date
            except ValueError:
                # אם הפורמט שגוי או התאריך משוגע, נשמור כ-None מבלי לרסק את השרת
                due_date = None

        task = Task(
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            due_date=due_date,
            priority=request.form.get("priority", "LOW"),
            user_id=current_user.id
        )
        db.session.add(task)
        db.session.commit()
        flash("המשימה נוצרה בהצלחה!", "success")
        return redirect(url_for("tasks.index"))

    # לוגיקת שליפה, סינון ועימוד משימות
    search_query = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    page = request.args.get("page", 1, type=int)
    sort_by = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")

    query = Task.query.filter_by(user_id=current_user.id)

    if search_query:
        query = query.filter((Task.title.contains(search_query)) | (Task.description.contains(search_query)))
    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    if sort_by == "due_date":
        query = query.order_by(Task.due_date.asc() if order == "asc" else Task.due_date.desc())
    elif sort_by == "priority":
        query = query.order_by(Task.priority.asc() if order == "asc" else Task.priority.desc())
    else:
        query = query.order_by(Task.created_at.asc() if order == "asc" else Task.created_at.desc())

    pagination = db.paginate(query, page=page, per_page=5, error_out=False)
    tasks = pagination.items

    return render_template("tasks.html", tasks=tasks, pagination=pagination, sort_by=sort_by, order=order)

# --- סימון משימה כבוצע ---
@bp.route("/done/<int:id>")
@login_required
def done(id):
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

# --- עריכת משימה ---
@bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    task = Task.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        due_date_str = request.form.get("due_date")
        due_date = None
        if due_date_str:
            try:
                parsed_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                if parsed_date.year <= 9999:
                    due_date = parsed_date
            except ValueError:
                due_date = None
                
        task.due_date = due_date
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
    todo = [t for t in tasks if t.status == "TODO" or not t.status]
    in_progress = [t for t in tasks if t.status == "IN_PROGRESS"]
    done = [t for t in tasks if t.status == "DONE"]
    return render_template("kanban.html", todo=todo, in_progress=in_progress, done=done)

# --- עדכון סטטוס גרירה (AJAX) ---
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

# --- API מזין ללוח השנה ---
@bp.route("/api/calendar_tasks")
@login_required
def calendar_tasks():
    tasks = Task.query.filter_by(user_id=current_user.id).filter(Task.due_date.isnot(None)).all()
    events = []
    for t in tasks:
        color = "#22c55e" if t.status == "DONE" else ("#ef4444" if t.priority == "HIGH" else ("#f59e0b" if t.priority == "MEDIUM" else "#3b82f6"))
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
# ✉️ מערכת איפוס סיסמה במייל (Password Reset)
# =========================================================

def send_reset_email(user):
    token = user.get_reset_token()
    reset_url = url_for('tasks.reset_token', token=token, _external=True)
    
    msg = Message('בקשה לאיפוס סיסמה - TaskManager',
                  sender='noreply@taskmanager.com',
                  recipients=[user.email])
    
    msg.body = f'''שלום {user.username},

כדי לאפס את הסיסמה שלך, לחץ על הקישור הבא (הקישור בתוקף ל-10 דקות בלבד):
{reset_url}

אם לא ביקשת לאפס את הסיסמה, אנא התעלם מהודעה זו ולא ייגרם שום שינוי.

בברכה,
צוות המערכת
'''
    mail.send(msg)

@bp.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('tasks.index'))
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        flash("אם האיมייל קיים במערכת, נשלחו אליו הוראות לאיפוס הסיסמה.", "info")
        return redirect(url_for('tasks.login'))
    return render_template("reset_request.html")

@bp.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('tasks.index'))
        
    user = User.verify_reset_token(token)
    if not user:
        flash("הקישור לאיפוס סיסמה שגוי או שפג תוקפו. אנא בקש קישור חדש.", "danger")
        return redirect(url_for('tasks.reset_request'))
        
    if request.method == "POST":
        password = request.form.get("password")
        user.set_password(password)
        db.session.commit()
        flash("הסיסמה שלך שונתה בהצלחה! כעת ניתן להתחבר עם הסיסמה החדשה.", "success")
        return redirect(url_for('tasks.login'))
        
    return render_template("reset_token.html")


# =========================================================
# 🛠️ כלי תחזוקה, סנכרון וחילוץ (Database Fix & Rescue)
# =========================================================

@bp.route("/fix-db")
def fix_db():
    output = []
    try:
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS "user" (
                id SERIAL PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL
            );
        '''))
        db.session.commit()
        output.append("✅ טבלת המשתמשים (user) נוצרה/אומתה בהצלחה.")
    except Exception as e:
        output.append(f"❌ שגיאה ביצירת טבלת המשתמשים: {e}")
        db.session.rollback()

    try:
        db.session.execute(text('ALTER TABLE task ADD COLUMN user_id INTEGER;'))
        db.session.commit()
        output.append("✅ עמודת user_id נוספה בהצלחה לטבלת המשימות.")
    except Exception as e:
        output.append("ℹ️ עמודת user_id כבר קיימת בטבלת המשימות.")
        db.session.rollback()

    return "<br>".join(output) + "<br><br><b>المערכת מוכנה! כעת כנס לעמוד הרישום ופתח חשבון קבוע.</b>"

@bp.route("/rescue")
def rescue():
    try:
        db.create_all()
        admin = User.query.filter_by(username='mv').first()
        
        if admin:
            admin.set_password("123456")
            db.session.commit()
            return f"✅ המשתמש '{admin.username}' נמצא במסד הנתונים! הסיסמה שלו אופסה בהצלחה ל- 123456. חזור לאתר והתחבר עם האימייל: {admin.email}"
        else:
            admin = User(username='mv', email='admin@test.com')
            admin.set_password("123456")
            db.session.add(admin)
            db.session.commit()
            return "✅ המשתמש לא היה קיים, אז יצרנו אותו עכשיו! כנס עם האימייל admin@test.com והסיסמה 123456."
            
    except Exception as e:
        db.session.rollback()
        return f"❌ שגיאה במסד הנתונים: {e}"

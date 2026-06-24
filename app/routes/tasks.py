# --- דלת אחורית לחילוץ המשתמש מבלי למחוק את מסד הנתונים ---
@bp.route("/rescue")
def rescue():
    try:
        # מוודא שכל הטבלאות קיימות
        db.create_all()
        
        # מחפש את המשתמש מנהל המערכת
        admin = User.query.filter_by(username='mv').first()
        
        if admin:
            # אם הוא קיים, פשוט מאפסים לו את הסיסמה בכוח
            admin.set_password("123456")
            db.session.commit()
            return f"✅ המשתמש '{admin.username}' נמצא במסד הנתונים! הסיסמה שלו אופסה בהצלחה ל- 123456. חזור לאתר והתחבר עם האימייל: {admin.email}"
        else:
            # אם הוא לא קיים, יוצרים אותו מאפס בצורה מושלמת
            admin = User(username='mv', email='admin@test.com')
            admin.set_password("123456")
            db.session.add(admin)
            db.session.commit()
            return "✅ המשתמש לא היה קיים, אז יצרנו אותו עכשיו! כנס עם האימייל admin@test.com והסיסמה 123456."
            
    except Exception as e:
        db.session.rollback()
        return f"❌ שגיאה במסד הנתונים: {e}"

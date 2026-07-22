# Task Manager - מערכת ניהול משימות היררכית

## מודל ההרשאות (עודכן)

שלוש רמות תפקיד:
- **admin (מנהל מערכת)** - רואה ומנהל את כל המשתמשים, המשימות והמחלקות במערכת.
- **manager (מנהל תחום)** - רואה ומנהל רק את המשתמשים והמשימות של המחלקה שאליה הוא משויך.
- **employee (עובד)** - רואה ומעדכן רק את המשימות שהוקצו לו אישית.

כל משתמש יכול להיות משויך ל-**מחלקה** (Department) ולבעל **מנהל ישיר** (manager_id, לצורך קו דיווח / עץ ארגוני).
ההרשאה לצפייה נקבעת לפי `role` + `department_id` (ראו `User.visible_users_query()` ב-`app/models/user.py`).

## הרצה מקומית
```
pip install -r requirements.txt
python run.py
```

## פריסה ל-Render
1. Push ל-GitHub (ודאו ש-`.env` לא נכלל - הוא ב-.gitignore).
2. חברו את הריפו ל-Render כ-Web Service.
3. הגדירו משתני סביבה ב-Render: `DATABASE_URL` (מ-Neon), `SECRET_KEY`, `MIGRATION_SECRET`.
4. ה-Start Command הוא `gunicorn run:app` (מוגדר כבר ב-Procfile).

## הרצת בדיקות אוטומטיות
```
pip install -r requirements-dev.txt
pytest -v
```
הבדיקות רצות על מסד SQLite זמני בלבד - לא נוגעות בנתונים אמיתיים. מכסות: הרשאות היררכיות, CSRF, הגנת מנהל אחרון, שדרוג סכימה אוטומטי, ופיצ'רים (משימות חוזרות, תגובות, תמונות).

## סביבת Staging (מומלץ להקמה)
כרגע כל שינוי נבדק ישירות מול נתוני הפרודקשן. מומלץ:
1. ליצור Web Service נוסף ב-Render בשם `task-manager-staging`, מחובר לאותו ריפו אבל ל-branch נפרד (למשל `staging`)
2. ליצור פרויקט Neon נפרד (או branch בתוך אותו פרויקט Neon - יש להם פיצ'ר branching) עם `DATABASE_URL` נפרד
3. לבדוק כל שינוי שם קודם, ולמזג ל-`main` (שמחובר לפרודקשן) רק אחרי שהוא עבד

## משתני סביבה נדרשים ב-Render
| משתנה | חובה | תיאור |
|---|---|---|
| `DATABASE_URL` | כן | חיבור ל-Neon Postgres |
| `SECRET_KEY` | כן | מחרוזת אקראית ייחודית לפרודקשן |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | לא | פרטי האדמין שנוצר אוטומטית אם אין אחד קיים |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` | לא | לשליחת מיילים (איפוס סיסמה + תזכורות). בלעדיהם שליחת מייל תיכשל בשקט |
| `REMINDER_SECRET` | לא | מפתח להפעלת `/api/send_due_reminders` דרך cron חיצוני |

## תזכורות יומיות אוטומטיות (מייל + מערכת)
כדי שהתזכורות באמת יישלחו כל בוקר, יש להגדיר קריאה יומית (למשל דרך cron-job.org החינמי) לכתובת:
```
https://<your-app>.onrender.com/api/send_due_reminders?key=<REMINDER_SECRET>&when=today
```
אפשר להוסיף גם קריאה נפרדת ביום שלפני עם `&when=tomorrow` לתזכורת מוקדמת. כל קריאה יוצרת גם התראה פנימית וגם מייל (אם למשתמש יש כתובת מייל מוגדרת).

⚠️ **וואטסאפ/SMS אוטומטיים** (בלי לחיצת אדם) **לא נתמכים** ללא שירות חיצוני בתשלום כמו Twilio - זה דורש אינטגרציה נפרדת. מה שכן קיים: כפתורי "שלח בוואטסאפ" בכל מקום רלוונטי (SOS, הודעות קבוצתיות, תזכורות בדשבורד) שפותחים קישור מוכן ללחיצה אחת.
| `ENABLE_ADMIN_TOOLS` + `MIGRATION_SECRET` | לא | מפעילים יחד את `/fix-db`, `/rescue`, `/upgrade-permissions` - השאירו כבויים בפרודקשן רגילה |

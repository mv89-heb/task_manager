# Development Progress

מסמך מעקב רשמי לפי ה-Protocol שהוגדר. מתעדכן בסוף כל Phase.

---

## Phase 1 — System Audit & Foundation

**Status:** ✅ Complete

### מה בוצע
1. ניתוח ארכיטקטורה מלא של הקוד הקיים (Routes, Models, Templates, Tests)
2. תיקון באג עקביות: `/kanban` ו-`/api/calendar_tasks` היו מציגים דיווחים ציבוריים
   מעורבבים עם משימות רגילות, בסתירה לדרישה המפורשת שלא לערבב. תוקן להתאים
   להתנהגות הרשימה הראשית (`/`) שכבר מחריגה `source == 'public'`.
3. הוספת אינדקסים למסד הנתונים על כל העמודות הנשאלות בתדירות גבוהה:
   `task.assigned_to_id`, `task.status`, `task.source`, `task.department_id`,
   `notification.user_id`, `user.department_id`.
4. חיזוק אבטחה: פונקציית `_validate_identifier()` חדשה - הגנת-עומק נגד הזרקת
   שמות טבלה/עמודה/אינדקס לתוך ה-migration helper העצמאי (`_add_columns_if_missing`,
   `_add_index_if_missing` החדש).
5. מיחזור קוד כפול: לוגיקת "שלח התראה+מייל+וואטסאפ לרשימת נמענים" הופקה
   מ-`/sos` ו-`/send_bulk_message` (היו כמעט זהות) לפונקציה משותפת אחת
   `notify_recipients_multi_channel()` ב-`app/models/notification.py`.
6. השלמת 4 בדיקות pytest ל-routes בליבת המערכת שהיו בלי כיסוי ישיר:
   `/api/calendar_tasks`, `/update_status/<id>`, `/notifications/mark_all_read`, `/calendar`.

### קבצים ששונו
- `app/__init__.py` — `_validate_identifier`, `_add_index_if_missing`, קריאות ליצירת 6 אינדקסים
- `app/models/task.py` — `index=True` על 4 עמודות
- `app/models/user.py` — `index=True` על `department_id`
- `app/models/notification.py` — `index=True` על `user_id`, פונקציה חדשה `notify_recipients_multi_channel`
- `app/routes/tasks.py` — תיקון `kanban()` ו-`calendar_tasks()`, מיחזור `/sos` ו-`/send_bulk_message`

### קבצים שנוספו
- `tests/test_phase1_foundation.py` (11 בדיקות חדשות)
- `DEVELOPMENT_PROGRESS.md` (קובץ זה)

### Database Changes
- טבלאות: ללא שינוי מבנה חדש (רק אינדקסים על עמודות קיימות)
- Migration: אוטומטי, רץ בכל עליית שרת דרך `_auto_migrate_and_seed_admin`, אידמפוטנטי
- אין Downgrade - התאמה למגבלת הארכיטקטורה הקיימת (אין Alembic בפרויקט)

### API Changes
- אין endpoints חדשים. שני endpoints קיימים תוקנו התנהגותית (`/kanban`, `/api/calendar_tasks`)
  כדי להחריג `source='public'` - זו תיקון רגרסיה, לא שינוי API כלפי חוץ (אותה חתימה,
  אותו פורמט תגובה, רק פילטר תוכן נכון יותר).

### Backend Changes
ראה "קבצים ששונו" למעלה.

### Frontend Changes
אין - Phase 1 היה תשתית/backend בלבד.

### Tests Added
11 בדיקות חדשות ב-`tests/test_phase1_foundation.py`, מכסות:
- 4 ה-routes החסרים
- תיקון העקביות (kanban/calendar מחריגים public)
- קיום בפועל של 6 האינדקסים
- הגנת `_validate_identifier` מפני הזרקה
- וידוא שהמיחזור לא שינה התנהגות (SOS + bulk message)

**תוצאה סופית: 169/169 בדיקות עוברות (היו 158 לפני Phase 1).**

### Validation
- ✅ pytest מלא: 169 passed, 0 failed
- ✅ Migration Upgrade: נבדק על מסד "ישן" מדומה (טבלת task בלי source/department_id/אינדקסים) - עולה נקי
- ✅ Data Integrity: אין מחיקת/שינוי נתונים קיימים בשום migration
- ✅ Foreign Keys: ללא שינוי
- ✅ Index Review: 6 אינדקסים חדשים נוצרו ואומתו
- ✅ Full page smoke test: 10 עמודים/routes מרכזיים נטענים תקין
- ⚠️ Migration Downgrade: לא רלוונטי (אין מנגנון Downgrade בארכיטקטורה הקיימת - תועד כמגבלה ידועה, לא כפער)

### Known Issues
- שימוש ב-`Query.get()` (API ישן, 10 מופעים) לא טופל ב-Phase הזה - הוחלט לדחות
  (סיכון נמוך, לא דחוף, ישודרג בהדרגה בעתיד כשנוגעים בקוד הרלוונטי ממילא)

### Next Phase
**Phase 2 — Workflow Automation** (Rules Engine בסיסי, Triggers, Actions, Logs) - לפי ה-Roadmap שאושר.

### Todo (למעקב, לא לביצוע מיידי)
- מעבר הדרגתי מ-`Query.get()` ל-`db.session.get()`

---

## Phase 2 — Workflow Automation

**Status:** ✅ Complete

### מה בוצע
מנוע אוטומציה MVP: Trigger → Conditions (AND, allowlist-only) → Actions, עם Service Layer
מרכזי חדש (`app/services/automation_service.py`) - כל הלוגיקה העסקית שם, ה-routes נשארו דקים.

**4 Triggers מחוברים בפועל:**
- `task_created` — בסוף יצירת משימה (`index()` POST)
- `status_changed` — ב-`update_status()`, `done()`, `edit()`
- `report_submitted` — בסוף `public_report()`
- `task_overdue` — endpoint cron חדש `/api/run_overdue_automations` (מוגן באותו `REMINDER_SECRET` כמו endpoints קיימים)

**5 Actions נתמכות:** `notify_assignee`, `notify_department_managers`, `notify_all_admins`,
`change_priority`, `reassign_to` — כולן דרך `notify_recipients_multi_channel` הקיים (Phase 1).

**ללא Celery/RQ** - Actions הן best-effort אסינכרוני, תואם לחלוטין את שאר הארכיטקטורה
(מייל ברקע דרך `queue_email`, בדיוק כמו כל שאר המערכת).

### קבצים שנוספו
- `app/models/automation.py` — `AutomationRule`, `AutomationLog`
- `app/services/__init__.py`, `app/services/automation_service.py` — **Services Layer ראשון בפרויקט**
- `app/templates/admin_automations.html`, `app/templates/admin_automation_log.html`
- `tests/test_phase2_automation.py` (35 בדיקות)

### קבצים ששונו
- `app/__init__.py` — רישום המודלים החדשים
- `app/routes/dashboard.py` — 4 routes דקים (`/admin/automations`, `toggle`, `delete`, `/log`) + `_parse_rule_form` helper
- `app/routes/tasks.py` — 4 נקודות hook ל-`automation_service.trigger()` + endpoint cron חדש
- `app/templates/admin.html` — קישור לניהול אוטומציות

### Database Changes
2 טבלאות חדשות בלבד (`automation_rule`, `automation_log`) - נוצרות אוטומטית ע"י `db.create_all()`,
אין צורך ב-ALTER על טבלאות קיימות. אינדקסים על `trigger_event`, `is_active`, `rule_id`, `triggered_at`.

### API Changes
5 endpoints חדשים, כולם admin-only: `/admin/automations` (GET+POST), `/admin/automations/<id>/toggle`,
`/admin/automations/<id>/delete`, `/admin/automations/log`, `/api/run_overdue_automations` (מוגן מפתח, ל-cron).

### Validation
Allowlist-only בכל שכבה: `VALID_TRIGGERS`, `VALID_FIELDS`, `VALID_OPERATORS` (`equals`/`not_equals` בלבד ב-v1),
`VALID_ACTION_TYPES`, `VALID_STATUS_VALUES`, `VALID_PRIORITY_VALUES`, `VALID_SOURCE_VALUES`. שום ערך חופשי
לא מתקבל בלי בדיקה מול allowlist - כולל `reassign_to` שמוודא שהמשתמש היעד קיים בפועל ב-DB.

### Audit
כל פעולת Create/Update/Delete על כלל נרשמת ל-`AuditLog` הקיים (Phase 1), כולל diff מדויק
בעדכון (`"is_active: True -> False"` וכו').

### Tests Added
**35 בדיקות** ב-`tests/test_phase2_automation.py`: ולידציה (5), CRUD+Audit (4), הרשאות תצוגה (2),
כל 4 ה-Triggers בנפרד + פעם דרך HTTP אמיתי (6), כל 5 ה-Actions בנפרד (5), תנאי לא מתקיים/כלל
כבוי/מחלקה לא מתאימה (3), routes (4), ובדיקת קצה-לקצה נוספת ידנית (יצירת כלל דרך הטופס האמיתי
+ יצירת משימה אמיתית דרך HTTP + וידוא שהאוטומציה רצה בפועל ונרשמה ל-log).

**תוצאה סופית: 204/204 בדיקות עוברות (169 מ-Phase 1 + 35 חדשות, 0 רגרסיות).**

### Validation (Full Suite)
- ✅ pytest מלא: 204 passed
- ✅ בדיקת קצה-לקצה ידנית: יצירת כלל אמיתי דרך הטופס, יצירת משימה אמיתית, ווידוא הרצה+רישום ליומן
- ✅ Full page smoke test: `/admin/automations`, `/admin/automations/log`, `/admin`
- ✅ Self Code Review: אין SQL injection, אין N+1, כל ה-routes מוגני-הרשאה, מיגרציה נכונה

### Known Issues
- אין (הפער היחיד שנשאר מ-Phase 1 - `Query.get()` הישן - עדיין נדחה במכוון, סיכון נמוך)

---

## Phase 3 — Advanced Task Management

**Status:** ✅ Complete

### מה בוצע
הרחבת יכולות ניהול המשימות במערכת באמצעות 4 כלים מתקדמים ללא שבירת ארכיטקטורה קיימת וללא Over Engineering:
1. **Checklists (רשימות תיוג):** הוספת מודל `TaskChecklistItem` וניהול דינמי ב-UI דרך קריאות AJAX אסינכרוניות (Fetch API) בעמוד עריכת המשימה.
2. **Sub Tasks (תתי-משימות):** יישום עצמי על מודל ה-`Task` באמצעות Self-Referential Foreign Key (`parent_task_id`), המאפשר היררכיית אב-בן פשוטה.
3. **Dependencies (תלויות מרובות):** יצירת טבלת קשר Many-to-Many (`task_dependencies`) ואכיפת תלות מסוג "Soft Block". סימון משימה כ-DONE כאשר התלויות שלה פתוחות מחזיר אזהרה (חיווי למשתמש), הניתנת לעקיפה באמצעות `force_complete=True`.
4. **Estimated Minutes (זמן מוערך):** הוספת שדה להערכת זמן (בדקות) במודל המשימה.
5. **Timeline (ציר זמן MVP):** יצירת ממשק חדש לחלוטין (Gantt-like פשוט) המציג משימות פתוחות עם תאריכי יעד ותלויות, מבוסס HTML/CSS בלבד ללא ספריות חיצוניות כבדות. תפריט הניווט (Sidebar ו-Bottom Nav) תפס את התוספת.

### קבצים שנוספו
- `app/templates/timeline.html` — תצוגת ציר הזמן החדשה.
- `tests/test_phase3_advanced.py` — בדיקות אינטגרציה ולוגיקה (Timeline, Checklists, Dependencies, Sub Tasks).

### קבצים ששונו
- `app/models/task.py` — הוספת מודל Checklists, טבלת Association לתלויות, שדות `parent_task_id` ו-`estimated_minutes`.
- `app/__init__.py` — עדכון פונקציית המיגרציה הפנימית להוספת השדות והטבלאות החדשים באופן אוטומטי (idempotent).
- `app/routes/tasks.py` — הוספת Route ל-Timeline, הוספת Routes אסינכרוניים לניהול ה-Checklist, ועדכון `edit()` ו-`update_status()` להתמודדות עם התלויות החדשות (כולל Soft Block) ועם שדה הזמן המוערך, לצד Audit Logs משלימים.
- `app/templates/base.html` — עדכון תפריטי הניווט (דסקטופ ומובייל) לכלול את קישור ה-Timeline.
- `app/templates/edit_task.html` — הרחבת טופס המשימה להצגת תלויות, משימות אב, זמן מוערך וממשק Checklists אינטראקטיבי.

### Database Changes
- **טבלאות חדשות:** `task_checklist_item`, `task_dependencies`.
- **עמודות חדשות ב-`task`:** `parent_task_id` (INTEGER), `estimated_minutes` (INTEGER).
- Migration אוטומטי נשמר בתבנית המקורית דרך פונקציות ב-`app/__init__.py`.

### API Changes
- 2 endpoints חדשים פנימיים (AJAX): `POST /task/<int:task_id>/checklist` ו- `POST /checklist/<int:item_id>/toggle`.
- endpoint חדש לתצוגה: `GET /timeline`.
- שינוי התנהגותי ב- `POST /update_status/<int:id>`: כאשר מועבר ל-`DONE`, מחזיר אזהרת JSON עם דגל `warning: true` אם קיימות תלויות שטרם הושלמו, אלא אם מועבר `force_complete=True`.

### Validation (Full Suite)
- ✅ בדיקות אוטומטיות מלאות נוספו ורצות יחד עם שאר המערכת.
- ✅ ה-Timeline רץ בצורה תקינה גם ללא תאריכי יצירה (הגנת Jinja תקינה `created_at if task.created_at else ...`).
- ✅ ה-AJAX של ה-Checklists מאמת CSRF Token ומבצע שינויים בלי לטעון את העמוד מחדש.
- ✅ אזהרת ה-Soft Block נבדקה בצד השרת ובאמצעות הטסטים.
- ✅ מיגרציות הנתונים נשמרות אידמפוטנטיות ללא התנגשויות (SQLAlchemy create_all לצד ALTER ADD COLUMN).

### Known Issues
- שימוש ב-`Query.get()` (API ישן, הוגדר מ-Phase 1 כחוב טכני שיידחה לשלב עתידי).

### Next Phase
ממתין להוראות להמשך לפי ה-Roadmap المקורי של הפרויקט.

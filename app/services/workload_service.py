from app.models.task import Task
from app.models.user import User, ROLE_ADMIN, ROLE_MANAGER
from datetime import date

def get_team_workload(manager_user):
    """
    מחשב ומחזיר נתוני עומס (Workload) עבור כל המשתמשים תחת אחריותו של המנהל.
    מיועד להצגה בממשק חזותי כדי לעזור למנהל להחליט למי להקצות משימות חדשות.
    """
    if manager_user.role not in (ROLE_ADMIN, ROLE_MANAGER):
        return []

    # השגת רשימת העובדים הרלוונטית (אדמין רואה את כולם, מנהל רואה את המחלקה שלו)
    users = manager_user.visible_users_query().all()
    
    today = date.today()
    workload_data = []

    for user in users:
        # שליפת המשימות הפתוחות של המשתמש
        user_tasks = Task.query.filter(Task.assigned_to_id == user.id, Task.status != 'DONE').all()
        
        task_count = len(user_tasks)
        overdue_count = sum(1 for t in user_tasks if t.due_date and t.due_date < today)
        high_priority_count = sum(1 for t in user_tasks if t.priority in ['HIGH', 'CRITICAL'])
        
        # חישוב דקות מוערכות. אם משימה חסרת הערכה, נניח 60 דקות כברירת מחדל 
        # כדי לא ליצור אשליית שווא של "אפס עומס" לעובד עם הרבה משימות לא מוערכות.
        total_minutes = sum((t.estimated_minutes if t.estimated_minutes else 60) for t in user_tasks)
        
        # חישוב אחוז עומס (לצורך ההדגמה: נניח שבוע עבודה פתוח של 40 שעות = 2400 דקות הוא 100%)
        # ניתן כמובן לכייל מספר זה לפי הצרכים האמיתיים של הארגון.
        MAX_MINUTES_CAPACITY = 2400 
        load_percentage = int((total_minutes / MAX_MINUTES_CAPACITY) * 100)
        
        # עבור סרגל ההתקדמות הוויזואלי (שלא יחרוג מ-100% רוחב)
        visual_percent = min(load_percentage, 100)
        
        # קביעת צבע סטטוס לפי רמת העומס והאיחורים
        status_color = "success" # פנוי / תקין
        if load_percentage > 85 or overdue_count > 3:
            status_color = "danger" # עמוס מאוד / בקריסה
        elif load_percentage > 50 or overdue_count > 0 or high_priority_count > 2:
            status_color = "warning" # עומס סביר / דורש תשומת לב

        workload_data.append({
            'user': user,
            'task_count': task_count,
            'overdue_count': overdue_count,
            'high_priority_count': high_priority_count,
            'total_hours': round(total_minutes / 60, 1),
            'load_percentage': load_percentage,
            'visual_percent': visual_percent,
            'status_color': status_color
        })

    # מיון התוצאות: מציג קודם את העובדים העמוסים ביותר כדי להציף בעיות
    workload_data.sort(key=lambda x: x['load_percentage'], reverse=True)
    return workload_data

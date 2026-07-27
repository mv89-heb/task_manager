from datetime import datetime, timedelta
from app.models.sla import SlaPolicy

def assign_sla(task):
    """
    מחשב ומקצה את תאריך חריגת ה-SLA (sla_breach_at) למשימה.
    המנוע בודק את כל חוקי ה-SLA, נותן 'ניקוד' לכל חוק לפי רמת הדיוק שלו אל מול המשימה,
    ומיישם את החוק הספציפי ביותר שניצח.
    """
    policies = SlaPolicy.query.all()
    
    best_policy = None
    max_score = -1
    
    for p in policies:
        score = 0
        match = True
        
        # בחינת התאמת עדיפות
        if p.priority:
            if p.priority == task.priority:
                score += 1
            else:
                match = False
                
        # בחינת התאמת מחלקה
        if p.department_id:
            if p.department_id == task.department_id:
                score += 1
            else:
                match = False
                
        # בחינת התאמת סוג משימה
        if p.task_type:
            if p.task_type == task.task_type:
                score += 1
            else:
                match = False
                
        # אם יש התאמה וזהו הציון הגבוה ביותר שנמצא עד כה, שומרים אותו
        if match and score > max_score:
            best_policy = p
            max_score = score
            
    if best_policy:
        base_time = task.created_at or datetime.utcnow()
        task.sla_breach_at = base_time + timedelta(hours=best_policy.max_hours)
    else:
        task.sla_breach_at = None

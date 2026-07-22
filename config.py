import os
from urllib.parse import urlsplit, urlunsplit

database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# Neon דורש חיבור מוצפן (SSL). אם ה-URL לא כולל כבר sslmode, נוסיף אותו כברירת מחדל.
if database_url and "sslmode" not in database_url:
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}sslmode=require"


def _force_direct_neon_endpoint(url):
    """
    ⚠️ ה-endpoint ה"pooled" של Neon (host עם סיומת "-pooler") חוסם פרמטרים
    מסוימים בזמן החיבור (כמו search_path), כי הוא מבוסס PgBouncer.
    כדי שהאפליקציה תמיד תתחבר בצורה יציבה - אם מזהים "-pooler." בכתובת,
    מסירים אותו אוטומטית ועוברים לחיבור הישיר. זה הופך אותנו לבלתי-תלויים
    בזה שה-DATABASE_URL שהודבק בפועל הוא pooled או direct.
    """
    parts = urlsplit(url)
    hostname = parts.hostname or ''
    if '-pooler.' not in hostname:
        return url

    new_host = hostname.replace('-pooler.', '.', 1)
    netloc = ''
    if parts.username:
        netloc += parts.username
        if parts.password:
            netloc += f':{parts.password}'
        netloc += '@'
    netloc += new_host
    if parts.port:
        netloc += f':{parts.port}'

    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


if database_url and database_url.startswith('postgresql'):
    database_url = _force_direct_neon_endpoint(database_url)


class Config:
    # כאן אנחנו מושכים את המפתח הסודי מ-Render
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-key-123')
    SQLALCHEMY_DATABASE_URI = database_url or 'sqlite:///db.sqlite3'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # הגדרות שליחת מייל (איפוס סיסמה + תזכורות) - נמשכות ממשתני סביבה.
    # ללא הגדרה, שליחת מייל תיכשל בשקט (Flask-Mail יזרוק שגיאת חיבור).
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME or 'noreply@taskmanager.local')

    # קריטי עבור Neon: מגדירים את search_path=public באופן מפורש בכל חיבור.
    # זה בטוח עכשיו כי אנחנו תמיד מתחברים ל-endpoint הישיר (לא ה-pooler),
    # שכן תומך בפרמטר הזה בזמן החיבור.
    if database_url and database_url.startswith('postgresql'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'options': '-csearch_path=public'}
        }

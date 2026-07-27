// Service Worker מינימלי - מטרתו היחידה היא לאפשר "התקנה למסך הבית" (PWA installability).
// בכוונה לא שומרים ב-cache נתונים דינמיים (משימות, דשבורד וכו') כדי לא להציג למשתמש
// מידע לא מעודכן/שגוי כשאין רשת. רק אייקונים וקבצי מניפסט נשמרים מקומית.

const STATIC_CACHE = 'taskmanager-static-v1';
const STATIC_ASSETS = [
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== STATIC_CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // רק בקשות לנכסים סטטיים קבועים (אייקונים/מניפסט) מוגשות מה-cache.
  // כל שאר הבקשות (עמודי HTML, API, נתונים) תמיד הולכות ישירות לרשת - בלי cache,
  // כדי שהמשתמש תמיד יראה נתונים עדכניים.
  if (STATIC_ASSETS.some((asset) => url.pathname === asset)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});

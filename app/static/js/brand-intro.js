/* Branded entry sequence — show once per browser tab session, login only */
(() => {
  const intro = document.getElementById('brandIntro');
  const form = document.getElementById('loginPanel');
  if (!intro || !form) return;

  // A failed login or a refresh may render /login again. Do not replay the
  // full-screen intro on every POST response or page reload in the same tab.
  const seenKey = 'taskManagerBrandIntroSeen';
  let alreadySeen = false;
  try {
    alreadySeen = window.sessionStorage.getItem(seenKey) === '1';
  } catch (_) {
    // Continue with the intro if browser storage is unavailable.
  }

  if (alreadySeen) {
    form.classList.add('is-visible');
    intro.remove();
    return;
  }

  try {
    window.sessionStorage.setItem(seenKey, '1');
  } catch (_) {
    // The animation still works; storage is only used to prevent replay.
  }

  document.documentElement.classList.add('intro-pending');
  form.setAttribute('aria-hidden', 'true');
  form.setAttribute('inert', '');

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const duration = reducedMotion ? 450 : 5200;
  let finished = false;

  const finish = () => {
    if (finished) return;
    finished = true;
    intro.classList.add('is-finished');
    document.documentElement.classList.remove('intro-pending');
    form.classList.add('is-visible');
    form.removeAttribute('aria-hidden');
    form.removeAttribute('inert');
    window.setTimeout(() => intro.remove(), 700);
  };

  const skip = intro.querySelector('[data-skip-intro]');
  if (skip) skip.addEventListener('click', finish, { once: true });
  window.setTimeout(finish, duration);
})();

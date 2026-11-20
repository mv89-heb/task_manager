/* Branded entry sequence — login only */
(() => {
  const intro = document.getElementById('brandIntro');
  const form = document.getElementById('loginPanel');
  if (!intro || !form) return;

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

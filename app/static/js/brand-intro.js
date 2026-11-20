/* Branded entry sequence — login only */
(() => {
  const intro=document.getElementById('brandIntro');
  const form=document.getElementById('loginPanel');
  if(!intro || !form) return;
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const duration=reduced?450:5200;
  const finish=() => {
    if(intro.classList.contains('is-finished')) return;
    intro.classList.add('is-finished');
    form.classList.add('is-visible');
    form.removeAttribute('aria-hidden');
    window.setTimeout(()=>intro.remove(),650);
  };
  form.setAttribute('aria-hidden','true');
  const skip=intro.querySelector('[data-skip-intro]');
  if(skip) skip.addEventListener('click',finish,{once:true});
  window.setTimeout(finish,duration);
})();

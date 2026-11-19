/* Gerak halus bersama: scroll ke bagian dengan easing + pil menu aktif yang meluncur.
   Dipakai oleh landing.html dan distro.html. */
(() => {
  'use strict';

  const root = document.documentElement;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fire = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));

  /* ===== Scroll beranimasi ===== */
  // Matikan smooth-scroll bawaan browser (CSS) supaya tidak berebut dengan animasi ini
  root.classList.add('js-scroll');

  const ease = t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2); // easeInOutCubic
  const offset = () => parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
  let raf = 0;

  const stop = () => {
    if (!raf) return;
    cancelAnimationFrame(raf); raf = 0;
    fire('smoothscroll:end');
  };

  const scrollToY = (target, done) => {
    stop();
    const start = window.scrollY;
    const max = root.scrollHeight - window.innerHeight;
    const y = Math.max(0, Math.min(target, max));
    const dist = y - start;
    if (Math.abs(dist) < 2 || reduce.matches) {
      window.scrollTo(0, y);
      if (done) done();
      return;
    }
    const dur = Math.min(1100, Math.max(500, Math.abs(dist) * .45));
    let t0 = null;
    const step = now => {
      if (t0 === null) t0 = now;
      const p = Math.min(1, (now - t0) / dur);
      window.scrollTo(0, start + dist * ease(p));
      if (p < 1) { raf = requestAnimationFrame(step); return; }
      raf = 0;
      fire('smoothscroll:end');
      if (done) done();
    };
    raf = requestAnimationFrame(step);
  };
  window.smoothScrollTo = scrollToY;

  // Pengguna menggulir sendiri saat animasi berjalan: serahkan kendali
  ['wheel', 'touchstart', 'keydown'].forEach(ev => window.addEventListener(ev, stop, { passive: true }));

  // Semua tautan #bagian dianimasikan
  document.addEventListener('click', e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const id = decodeURIComponent(a.getAttribute('href').slice(1));
    let y = 0;
    if (id) {
      const el = document.getElementById(id);
      if (!el) return;
      y = el.getBoundingClientRect().top + window.scrollY - offset();
    }
    e.preventDefault();
    fire('smoothscroll:start', { id });
    scrollToY(y, () => {
      try { history.replaceState(null, '', id ? '#' + id : window.location.pathname + window.location.search); } catch { /* abaikan */ }
    });
  });

  /* ===== Pil penanda menu aktif yang meluncur ===== */
  window.NavPill = (container, selector) => {
    const pill = document.createElement('span');
    pill.className = 'nav-pill';
    pill.setAttribute('aria-hidden', 'true');
    container.prepend(pill);
    container.classList.add('has-pill');
    let current = null;

    const place = () => {
      if (!current || !current.offsetWidth) return;
      pill.style.width = current.offsetWidth + 'px';
      pill.style.height = current.offsetHeight + 'px';
      pill.style.transform = `translate(${current.offsetLeft}px,${current.offsetTop}px)`;
      if (!pill.classList.contains('ready')) requestAnimationFrame(() => pill.classList.add('ready'));
    };
    const set = el => {
      if (el === current) return;
      current = el;
      if (!el) { pill.classList.remove('ready'); return; }
      place();
    };
    window.addEventListener('resize', place);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(place);
    const collapse = container.closest('.collapse');
    if (collapse) collapse.addEventListener('shown.bs.collapse', place);
    return { set, place, items: () => [...container.querySelectorAll(selector)] };
  };
})();

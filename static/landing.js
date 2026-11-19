(() => {
  'use strict';

  /* ===== Status login (sesi = cookie HttpOnly di server; ditanyakan lewat API) ===== */
  const btnMasuk = document.getElementById('btnMasuk');
  const userBox  = document.getElementById('userBox');
  const userName = document.getElementById('userName');

  const renderAuth = user => {
    document.body.classList.toggle('guest', !user);
    btnMasuk.classList.toggle('d-none', !!user);
    userBox.classList.toggle('d-none', !user);
    userName.textContent = user ? `Halo, ${user.name}` : '';
  };
  document.getElementById('btnKeluar').addEventListener('click', async () => {
    await api.logout();
    renderAuth(null);
  });
  renderAuth(null);
  api.me().then(renderAuth).catch(() => { /* server tak terjangkau: tampil sebagai tamu */ });

  /* ===== Menu aktif sesuai posisi scroll ===== */
  const links = [...document.querySelectorAll('.site-nav .nav-link')];
  const pill = window.NavPill ? window.NavPill(document.querySelector('.site-nav .navbar-nav'), '.nav-link') : null;
  let lockSpy = false; // saat animasi scroll karena klik menu, jangan loncat-loncat lewat bagian lain
  const setActive = id => {
    let active = null;
    links.forEach(a => {
      const on = a.getAttribute('href') === '#' + id;
      if (on) active = a;
      a.classList.toggle('active', on);
      on ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
    });
    if (pill) pill.set(active);
  };
  const spy = new IntersectionObserver(entries => {
    if (lockSpy) return;
    entries.forEach(e => e.isIntersecting && setActive(e.target.id));
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['beranda', 'about', 'contact'].forEach(id => spy.observe(document.getElementById(id)));
  document.addEventListener('smoothscroll:start', e => {
    lockSpy = true;
    if (e.detail && ['beranda', 'about', 'contact'].includes(e.detail.id)) setActive(e.detail.id); // pil langsung meluncur ke tujuan
  });
  document.addEventListener('smoothscroll:end', () => { lockSpy = false; });

  /* ===== Navbar: garis bawah saat di-scroll + tutup menu mobile ===== */
  const nav = document.getElementById('siteNav');

  const menu = document.getElementById('menu');

  /* ===== Navbar: tersembunyi di paling atas, muncul beranimasi saat digulir ===== */
  const SHOW_AFTER = 60;   // px gulir sebelum navbar muncul
  const HIDE_BELOW = 20;   // baru sembunyi lagi di bawah ini (hysteresis: tidak kedip di sekitar batas)
  let peek = false, peekTimer, shownByScroll = window.scrollY > SHOW_AFTER, ticking = false;
  const updateNav = () => {
    const y = window.scrollY;
    if (y > SHOW_AFTER) shownByScroll = true; else if (y < HIDE_BELOW) shownByScroll = false;
    nav.classList.toggle('nav-hidden', !(shownByScroll || peek || menu.classList.contains('show')));
    nav.classList.toggle('scrolled', y > 10);
  };
  const peekNav = (ms) => {            // munculkan sementara saat masih di atas
    peek = true; updateNav();
    clearTimeout(peekTimer);
    if (ms) peekTimer = setTimeout(() => { peek = false; updateNav(); }, ms);
  };
  window.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { ticking = false; updateNav(); });
  }, { passive: true });
  menu.addEventListener('hidden.bs.collapse', updateNav);
  // Mouse mendekati tepi atas / tombol Tab / ketuk tepi atas layar = tampilkan sementara
  document.addEventListener('mousemove', e => {
    if (shownByScroll) return;
    if (e.clientY < 48) peekNav();
    else if (peek && e.clientY > nav.getBoundingClientRect().bottom + 24) { peek = false; updateNav(); }
  }, { passive: true });
  document.addEventListener('pointerdown', e => {
    if (e.pointerType !== 'mouse' && e.clientY < 64 && !shownByScroll) peekNav(4500);
  }, { passive: true });
  nav.addEventListener('focusin', () => peekNav());
  nav.addEventListener('focusout', e => { if (!nav.contains(e.relatedTarget)) { peek = false; updateNav(); } });
  updateNav();
  links.forEach(a => a.addEventListener('click', () => {
    if (menu.classList.contains('show')) bootstrap.Collapse.getOrCreateInstance(menu).hide();
  }));


  /* ===== Menu yang belum dibuat (Profil) ===== */
  const toast = document.getElementById('toastSoon');
  let toastTimer;
  document.querySelectorAll('[data-soon]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    toast.textContent = `Halaman ${a.dataset.soon} belum dibuat.`;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    if (menu.classList.contains('show')) bootstrap.Collapse.getOrCreateInstance(menu).hide();
  }));

  /* ===== Kembali ke atas ===== */
  const toTop = document.getElementById('toTop');
  window.addEventListener('scroll', () => toTop.classList.toggle('show', window.scrollY > 600), { passive: true });
  document.querySelectorAll('[data-top]').forEach(b =>
    b.addEventListener('click', () => (window.smoothScrollTo ? window.smoothScrollTo(0) : window.scrollTo({ top: 0, behavior: 'smooth' }))));


  /* ===== Kartu polaroid: foto distro berganti otomatis tiap 3 detik ===== */
  const DISTROS = {
    ubuntu: { name: 'Ubuntu',     tag: 'Pemula',   img: 'img/tux-ubuntu.jpg',  pos: '50% 40%', alt: 'Tux memegang CD Ubuntu',
              desc: 'Pilihan populer pemula: mudah dipasang, komunitas besar.' },
    debian: { name: 'Debian',     tag: 'Stabil',   img: 'img/debian-lain.jpg', pos: '50% 40%', alt: 'Karakter anime memakai laptop berlogo Debian',
              desc: 'Sangat stabil. Ubuntu dibangun di atasnya.' },
    mint:   { name: 'Linux Mint', tag: 'Pemula',   img: 'img/tux-mint.jpg',    pos: '50% 55%', alt: 'Tux memegang CD Linux Mint',
              desc: 'Akrab bagi pengguna Windows, nyaman sehari-hari.' },
    kali:   { name: 'Kali Linux', tag: 'Keamanan', img: 'img/kali.jpg',        pos: '50% 50%', alt: 'Logo Kali Linux di depan bulan',
              desc: 'Khusus untuk pengujian dan belajar keamanan siber.' },
    arch:   { name: 'Arch Linux', tag: 'Mahir',    img: 'img/tux-arch.jpg',    pos: '50% 40%', alt: 'Tux memegang CD Arch Linux',
              desc: 'Ringan dan fleksibel, rakit sistemmu sendiri.' },
    fedora: { name: 'Fedora',     tag: 'Terbaru',  img: 'img/fedora.jpg',      pos: '20% 50%', alt: 'Logo Fedora dengan ilustrasi karakter anime',
              desc: 'Teknologi terbaru yang tetap rapi dan stabil.' }
  };
  const INTERVAL = 3000;        // ms antar foto
  const FIRST_DELAY = 450;      // ms kosong sebelum foto pertama muncul
  const TILT = [-8, 6, -5, 8, -7, 5]; // kemiringan tiap kartu (derajat)
  const keys = Object.keys(DISTROS);
  const stage = document.getElementById('stage');
  const dotsEl = document.getElementById('dots');
  stage.parentElement.style.setProperty('--dur', INTERVAL + 'ms');
  keys.forEach(k => { new Image().src = DISTROS[k].img; }); // muat lebih dulu agar mulus

  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; };
  const restart = (node, cls) => { node.classList.remove(cls); void node.offsetWidth; node.classList.add(cls); };

  const build = i => {
    const d = DISTROS[keys[i]];
    const card = el('figure', 'pol');
    card.style.setProperty('--r', TILT[i % TILT.length] + 'deg');
    const photo = el('div', 'pol-photo');
    const img = new Image();
    img.src = d.img; img.alt = d.alt; img.style.objectPosition = d.pos; img.decoding = 'async';
    photo.appendChild(img);
    const cap = el('figcaption');
    const name = el('div', 'pol-name', d.name);
    name.appendChild(el('span', 'pol-tag', d.tag));
    cap.append(name, el('p', 'pol-desc', d.desc));
    card.append(photo, cap);
    return card;
  };

  const dots = keys.map((k, i) => {
    const b = el('button', 'dot');
    b.type = 'button';
    b.setAttribute('aria-label', `Tampilkan ${DISTROS[k].name}`);
    b.appendChild(document.createElement('i'));
    b.addEventListener('click', () => { show(i); play(); });
    dotsEl.appendChild(b);
    return b;
  });

  let idx = -1, current = null, timer = null;
  const show = i => {
    idx = (i + keys.length) % keys.length;
    const next = build(idx);
    if (current) {
      const old = current;
      old.classList.add('out');
      setTimeout(() => old.remove(), 700);
    }
    stage.appendChild(next);
    current = next;
    dots.forEach((d, n) => { d.classList.remove('on'); d.removeAttribute('aria-current'); if (n === idx) { restart(d, 'on'); d.setAttribute('aria-current', 'true'); } });
  };
  const play = () => { clearInterval(timer); timer = setInterval(() => show(idx + 1), INTERVAL); };

  // Awal: kosong sebentar, lalu foto pertama muncul dan siklus berjalan
  setTimeout(() => { show(0); play(); }, FIRST_DELAY);
  // Hemat tenaga: berhenti saat tab tidak terlihat
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { clearInterval(timer); timer = null; }
    else if (idx >= 0) play();
  });

  /* ===== Form kontak (dikirim ke server) ===== */
  const form = document.getElementById('contactForm');
  const alertBox = document.getElementById('contactAlert');
  const showMsg = (type, text) => {
    alertBox.innerHTML = '';
    const el = document.createElement('div');
    el.className = `alert alert-${type}`;
    el.textContent = text;
    alertBox.appendChild(el);
  };
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const fields = form.querySelectorAll('.form-control');
    fields.forEach(f => f.classList.toggle('is-invalid', !f.checkValidity()));
    if (!form.checkValidity()) return showMsg('danger', 'Lengkapi nama, email yang valid, dan pesan.');
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await api.post('/api/contact', { name: form.elements.nama.value, email: form.elements.email.value, message: form.elements.pesan.value });
      showMsg('success', 'Terima kasih! Pesanmu sudah kami terima.');
      form.reset();
    } catch (err) {
      showMsg('danger', err.message);
    } finally { btn.disabled = false; }
  });
  form.querySelectorAll('.form-control').forEach(f =>
    f.addEventListener('input', () => f.classList.toggle('is-invalid', f.value !== '' && !f.checkValidity())));
})();
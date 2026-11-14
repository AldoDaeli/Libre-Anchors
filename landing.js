(() => {
  'use strict';

  /* ===== Status login (dibuat oleh app.js di halaman login) ===== */
  const SESSION_KEY = 'session';
  const getSession = () => {
    try { return JSON.parse(localStorage.getItem(SESSION_KEY)); } catch { return null; }
  };
  const btnMasuk = document.getElementById('btnMasuk');
  const userBox  = document.getElementById('userBox');
  const userName = document.getElementById('userName');

  const renderAuth = () => {
    const s = getSession();
    btnMasuk.classList.toggle('d-none', !!s);
    userBox.classList.toggle('d-none', !s);
    userName.textContent = s ? `Halo, ${s.name}` : '';
  };
  document.getElementById('btnKeluar').addEventListener('click', () => {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* abaikan */ }
    renderAuth();
  });
  renderAuth();

  /* ===== Menu aktif sesuai posisi scroll ===== */
  const links = [...document.querySelectorAll('.site-nav .nav-link')];
  const setActive = id => links.forEach(a => {
    const on = a.getAttribute('href') === '#' + id;
    a.classList.toggle('active', on);
    on ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current');
  });
  const spy = new IntersectionObserver(entries => {
    entries.forEach(e => e.isIntersecting && setActive(e.target.id));
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['beranda', 'about', 'contact'].forEach(id => spy.observe(document.getElementById(id)));

  /* ===== Navbar: garis bawah saat di-scroll + tutup menu mobile ===== */
  const nav = document.querySelector('.site-nav');
  const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 10);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  const menu = document.getElementById('menu');
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
    b.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' })));


  /* ===== Klik nama distro: gambar tampil di dalam terminal ===== */
  const DISTROS = {
    ubuntu: { name: 'Ubuntu',     tag: 'Pemula',   img: 'img/tux-ubuntu.jpg',  pos: '50% 40%', alt: 'Tux memegang CD Ubuntu' },
    debian: { name: 'Debian',     tag: 'Stabil',   img: 'img/debian-lain.jpg', pos: '50% 40%', alt: 'Karakter anime memakai laptop berlogo Debian' },
    mint:   { name: 'Linux Mint', tag: 'Pemula',   img: 'img/tux-mint.jpg',    pos: '50% 55%', alt: 'Tux memegang CD Linux Mint' },
    kali:   { name: 'Kali Linux', tag: 'Keamanan', img: 'img/kali.jpg',        pos: '50% 50%', alt: 'Logo Kali Linux di depan bulan' },
    arch:   { name: 'Arch Linux', tag: 'Mahir',    img: 'img/tux-arch.jpg',    pos: '50% 40%', alt: 'Tux memegang CD Arch Linux' },
    fedora: { name: 'Fedora',     tag: 'Terbaru',  img: 'img/fedora.jpg',      pos: '20% 50%', alt: 'Logo Fedora dengan ilustrasi karakter anime' }
  };
  const plate = document.querySelector('.plate');
  const shot = document.getElementById('shot');
  const shotImg = document.getElementById('shotImg');
  const hint = document.querySelector('.plate-hint');
  const HINT_DEFAULT = hint.textContent;
  const chips = [...document.querySelectorAll('[data-distro]')];
  let current = null;

  const showTerminal = () => {
    current = null;
    plate.classList.remove('show-shot');
    chips.forEach(c => { c.classList.remove('on'); c.setAttribute('aria-pressed', 'false'); });
    hint.textContent = HINT_DEFAULT;
  };
  const showDistro = key => {
    const d = DISTROS[key];
    if (!d) return;
    current = key;
    shotImg.src = d.img; shotImg.alt = d.alt; shotImg.style.objectPosition = d.pos;
    document.getElementById('shotCmd').textContent = `user@linux:~$ open ${key}.jpg`;
    document.getElementById('shotName').textContent = `${d.name} · ${d.tag}`;
    plate.classList.add('show-shot');
    chips.forEach(c => { const on = c.dataset.distro === key; c.classList.toggle('on', on); c.setAttribute('aria-pressed', String(on)); });
    hint.textContent = 'Klik lagi untuk kembali ke terminal';
  };
  chips.forEach(chip => chip.addEventListener('click', () =>
    chip.dataset.distro === current ? showTerminal() : showDistro(chip.dataset.distro)));
  shot.addEventListener('click', showTerminal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && current) showTerminal(); });

  /* ===== Form kontak (statis: belum terhubung ke server) ===== */
  const form = document.getElementById('contactForm');
  const alertBox = document.getElementById('contactAlert');
  form.addEventListener('submit', e => {
    e.preventDefault();
    const fields = form.querySelectorAll('.form-control');
    fields.forEach(f => f.classList.toggle('is-invalid', !f.checkValidity()));
    alertBox.innerHTML = '';
    const el = document.createElement('div');
    if (!form.checkValidity()) {
      el.className = 'alert alert-danger';
      el.textContent = 'Lengkapi nama, email yang valid, dan pesan.';
    } else {
      el.className = 'alert alert-success';
      el.textContent = 'Terima kasih! Pesanmu sudah kami terima.';
      form.reset();
    }
    alertBox.appendChild(el);
  });
  form.querySelectorAll('.form-control').forEach(f =>
    f.addEventListener('input', () => f.classList.toggle('is-invalid', f.value !== '' && !f.checkValidity())));
})();
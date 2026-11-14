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


  /* ===== Popup gambar distro (klik label di piringan) ===== */
  const DISTROS = {
    ubuntu: { name: 'Ubuntu',     tag: 'Pemula',   img: 'img/tux-ubuntu.jpg',  pos: '50% 40%', alt: 'Tux memegang CD Ubuntu',
              desc: 'Pilihan populer untuk pemula: instalasi mudah, komunitas besar, dan banyak panduan.' },
    debian: { name: 'Debian',     tag: 'Stabil',   img: 'img/debian-lain.jpg', pos: '50% 35%', alt: 'Karakter anime memakai laptop berlogo Debian',
              desc: 'Dikenal sangat stabil. Banyak distro lain, termasuk Ubuntu, dibangun di atasnya.' },
    mint:   { name: 'Linux Mint', tag: 'Pemula',   img: 'img/tux-mint.jpg',    pos: '50% 62%', alt: 'Tux memegang CD Linux Mint',
              desc: 'Tampilannya akrab bagi pengguna Windows, stabil dan nyaman dipakai sehari-hari.' },
    kali:   { name: 'Kali Linux', tag: 'Keamanan', img: 'img/kali.jpg',        pos: '50% 50%', alt: 'Logo Kali Linux di depan bulan',
              desc: 'Dibuat khusus untuk pengujian keamanan. Cocok untuk belajar keamanan siber.' },
    arch:   { name: 'Arch Linux', tag: 'Mahir',    img: 'img/tux-arch.jpg',    pos: '50% 40%', alt: 'Tux memegang CD Arch Linux',
              desc: 'Ringan dan fleksibel. Cocok bagi yang ingin merakit sistemnya sendiri sambil belajar.' },
    fedora: { name: 'Fedora',     tag: 'Terbaru',  img: 'img/fedora.jpg',      pos: '50% 50%', alt: 'Logo Fedora dengan ilustrasi karakter anime',
              desc: 'Mengusung teknologi terbaru dengan tetap rapi dan stabil, didukung komunitas dan Red Hat.' }
  };
  const modalEl = document.getElementById('distroModal');
  const dImg = document.getElementById('distroImg');
  document.querySelectorAll('[data-distro]').forEach(chip => chip.addEventListener('click', () => {
    const d = DISTROS[chip.dataset.distro];
    if (!d) return;
    dImg.src = d.img; dImg.alt = d.alt; dImg.style.objectPosition = d.pos;
    document.getElementById('distroTitle').textContent = d.name;
    document.getElementById('distroTag').textContent = d.tag;
    document.getElementById('distroDesc').textContent = d.desc;
    bootstrap.Modal.getOrCreateInstance(modalEl).show();
  }));

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
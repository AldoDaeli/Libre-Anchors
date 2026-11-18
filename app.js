(() => {
  'use strict';

  /* ===== Akun dummy (ganti dengan backend sungguhan nanti) ===== */
  const DEMO_ACCOUNTS = [
    { name: 'Demo User', email: 'demo@example.com', password: 'demo123' },
    { name: 'Admin',     email: 'admin@example.com', password: 'admin123' }
  ];
  const STORAGE_KEY = 'dummyAccounts';

  const card    = document.getElementById('card');
  const formIn  = document.getElementById('formSignIn');
  const formUp  = document.getElementById('formSignUp');

  /* ----- Penyimpanan akun hasil pendaftaran (localStorage) ----- */
  const loadSaved = () => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
    catch { return []; }
  };
  const saveAccount = acc => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify([...loadSaved(), acc])); }
    catch { /* storage tidak tersedia: akun hanya berlaku di sesi ini */ memory.push(acc); }
  };
  const memory = [];
  // Data hasil simpanan (mis. dari halaman profil) didahulukan agar bisa menimpa akun demo
  const allAccounts = () => [...memory, ...loadSaved(), ...DEMO_ACCOUNTS];
  const findByEmail = email => allAccounts().find(a => a.email === email.trim().toLowerCase());

  /* ----- Notifikasi dalam form ----- */
  const notify = (form, type, text) => {
    const slot = form.querySelector('.alert-slot');
    slot.innerHTML = '';
    if (!text) return;
    const el = document.createElement('div');
    el.className = `alert alert-${type}`;
    el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    el.textContent = text;
    slot.appendChild(el);
  };

  /* ----- Switch Masuk <-> Daftar ----- */
  const setMode = mode => {
    card.classList.toggle('right-active', mode === 'signup');
    notify(formIn); notify(formUp);
    const target = mode === 'signup' ? formUp : formIn;
    setTimeout(() => target.querySelector('input')?.focus({ preventScroll: true }), 600);
  };
  document.querySelectorAll('[data-switch]').forEach(btn =>
    btn.addEventListener('click', () => setMode(btn.dataset.switch)));

  /* ----- Validasi tampilan ----- */
  const markInvalid = form =>
    form.querySelectorAll('.form-control').forEach(i => i.classList.toggle('is-invalid', !i.checkValidity()));
  document.querySelectorAll('.form-control').forEach(i =>
    i.addEventListener('input', () => i.classList.toggle('is-invalid', i.value !== '' && !i.checkValidity())));

  /* ----- Masuk ----- */
  formIn.addEventListener('submit', e => {
    e.preventDefault();
    markInvalid(formIn);
    if (!formIn.checkValidity()) return notify(formIn, 'danger', 'Isi email dan kata sandi dengan benar.');

    const { email, password } = formIn.elements;
    const user = findByEmail(email.value);
    if (!user || user.password !== password.value) {
      return notify(formIn, 'danger', 'Email atau kata sandi salah.');
    }
    goHome(user);
  });

  /* ----- Daftar ----- */
  formUp.addEventListener('submit', e => {
    e.preventDefault();
    markInvalid(formUp);
    if (!formUp.checkValidity()) return notify(formUp, 'danger', 'Lengkapi data. Kata sandi minimal 6 karakter.');

    const { name, email, password } = formUp.elements;
    if (findByEmail(email.value)) return notify(formUp, 'danger', 'Email sudah terdaftar. Silakan masuk.');

    saveAccount({ name: name.value.trim(), email: email.value.trim().toLowerCase(), password: password.value });
    const registered = email.value.trim().toLowerCase();
    formUp.reset();
    setMode('signin');
    formIn.elements.email.value = registered;
    notify(formIn, 'success', 'Akun dibuat! Silakan masuk.');
  });

  /* ----- Isi otomatis akun demo ----- */
  document.getElementById('fillDemo').addEventListener('click', () => {
    formIn.elements.email.value = DEMO_ACCOUNTS[0].email;
    formIn.elements.password.value = DEMO_ACCOUNTS[0].password;
    formIn.querySelectorAll('.form-control').forEach(i => i.classList.remove('is-invalid'));
    notify(formIn);
  });

  /* ----- Setelah masuk: simpan sesi, langsung ke beranda ----- */
  const SESSION_KEY = 'session';
  /* Tujuan setelah masuk: halaman asal (?next=...) atau beranda.
     Hanya nama file .html di folder yang sama yang diterima (mencegah redirect ke situs lain). */
  const nextUrl = () => {
    const n = new URLSearchParams(window.location.search).get('next') || '';
    return /^[a-z0-9_-]+\.html(\?[a-z0-9_=&-]*)?$/i.test(n) ? n : 'landing.html';
  };
  function goHome(user) {
    try { localStorage.setItem(SESSION_KEY, JSON.stringify({ name: user.name, email: user.email })); } catch { /* abaikan */ }
    window.location.href = nextUrl();
  }

  /* Jika sudah login, tidak perlu di halaman ini */
  try {
    const s = JSON.parse(localStorage.getItem(SESSION_KEY));
    if (s && s.name) window.location.replace(nextUrl());
  } catch { /* abaikan */ }

  /* Datang dari halaman yang butuh login: beri tahu */
  if (nextUrl().startsWith('distro.html')) notify(formIn, 'info', 'Masuk dulu untuk membaca materi lengkap distro.');
})();
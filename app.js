(() => {
  'use strict';

  /* ===== Akun dummy (ganti dengan backend sungguhan nanti) ===== */
  const DEMO_ACCOUNTS = [
    { name: 'Demo User', email: 'demo@example.com', password: 'demo123' },
    { name: 'Admin',     email: 'admin@example.com', password: 'admin123' }
  ];
  const STORAGE_KEY = 'dummyAccounts';

  const card    = document.getElementById('card');
  const welcome = document.getElementById('welcome');
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
  const allAccounts = () => [...DEMO_ACCOUNTS, ...loadSaved(), ...memory];
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
    showWelcome(user);
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

  /* ----- Tampilan setelah masuk ----- */
  const SESSION_KEY = 'session';
  function showWelcome(user) {
    try { localStorage.setItem(SESSION_KEY, JSON.stringify({ name: user.name, email: user.email })); } catch { /* abaikan */ }
    document.getElementById('welcomeName').textContent = `Halo, ${user.name}!`;
    document.getElementById('welcomeEmail').textContent = user.email;
    document.getElementById('welcomeInitial').textContent = user.name.charAt(0).toUpperCase();
    welcome.classList.add('show');
    welcome.setAttribute('aria-hidden', 'false');
    document.getElementById('logout').focus({ preventScroll: true });
  }
  document.getElementById('logout').addEventListener('click', () => {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* abaikan */ }
    welcome.classList.remove('show');
    welcome.setAttribute('aria-hidden', 'true');
    formIn.reset(); notify(formIn, 'success', 'Anda sudah keluar.');
  });

  /* Jika sudah login, langsung tampilkan sapaan */
  try {
    const s = JSON.parse(localStorage.getItem(SESSION_KEY));
    if (s && s.name) showWelcome(s);
  } catch { /* abaikan */ }
})();
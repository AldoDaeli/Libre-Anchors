(() => {
  'use strict';

  const SESSION_KEY = 'session';
  const ACCOUNTS_KEY = 'dummyAccounts';
  const PROFILE_KEY = 'profileExtra'; // { [email]: { address, city } }

  const DEMO_ACCOUNTS = [
    { name: 'Demo User', email: 'demo@example.com', password: 'demo123' },
    { name: 'Admin',     email: 'admin@example.com', password: 'admin123' }
  ];

  const read = (key, fallback) => {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  };
  const write = (key, val) => {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch { /* abaikan */ }
  };

  /* ----- Wajib login ----- */
  const session = read(SESSION_KEY, null);
  if (!session || !session.email) {
    window.location.replace('login.html');
    return;
  }

  const form = document.getElementById('profileForm');
  const alertBox = document.getElementById('profileAlert');
  const fields = form.querySelectorAll('.form-control');

  const notify = (type, text) => {
    alertBox.innerHTML = '';
    if (!text) return;
    const el = document.createElement('div');
    el.className = `alert alert-${type}`;
    el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    el.textContent = text;
    alertBox.appendChild(el);
  };

  /* ----- Navbar: nama & keluar ----- */
  const renderHeader = s => {
    document.getElementById('userName').textContent = `Halo, ${s.name}`;
    document.getElementById('avatar').textContent = s.name.charAt(0).toUpperCase();
    document.getElementById('profilName').textContent = s.name;
    document.getElementById('profilEmail').textContent = s.email;
  };
  document.getElementById('btnKeluar').addEventListener('click', () => {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* abaikan */ }
    window.location.href = 'landing.html';
  });

  /* ----- Isi form dari data tersimpan ----- */
  const extras = () => read(PROFILE_KEY, {});
  const fill = s => {
    const ex = extras()[s.email] || {};
    form.elements.name.value = s.name;
    form.elements.email.value = s.email;
    form.elements.password.value = '';
    form.elements.city.value = ex.city || '';
    form.elements.address.value = ex.address || '';
  };
  renderHeader(session);
  fill(session);

  /* ----- Validasi tampilan ----- */
  fields.forEach(f => f.addEventListener('input', () =>
    f.classList.toggle('is-invalid', f.value !== '' && !f.checkValidity())));

  /* ----- Simpan ----- */
  form.addEventListener('submit', e => {
    e.preventDefault();
    fields.forEach(f => f.classList.toggle('is-invalid', !f.checkValidity()));
    if (!form.checkValidity()) {
      return notify('danger', 'Lengkapi nama dan email yang valid. Kata sandi baru minimal 6 karakter.');
    }

    const oldEmail = session.email;
    const name = form.elements.name.value.trim();
    const email = form.elements.email.value.trim().toLowerCase();
    const newPass = form.elements.password.value;

    const saved = read(ACCOUNTS_KEY, []);
    const taken = [...DEMO_ACCOUNTS, ...saved].some(a => a.email === email && a.email !== oldEmail);
    if (taken) return notify('danger', 'Email sudah dipakai akun lain.');

    // Akun saat ini (dari simpanan, atau akun demo)
    const current = saved.find(a => a.email === oldEmail) || DEMO_ACCOUNTS.find(a => a.email === oldEmail);
    const password = newPass || (current ? current.password : '');

    // Ganti entri lama dengan yang baru (akun demo ikut "ditimpa" lewat simpanan)
    const next = saved.filter(a => a.email !== oldEmail && a.email !== email);
    next.push({ name, email, password });
    write(ACCOUNTS_KEY, next);

    // Data tambahan (alamat & kota)
    const ex = extras();
    delete ex[oldEmail];
    ex[email] = { city: form.elements.city.value.trim(), address: form.elements.address.value.trim() };
    write(PROFILE_KEY, ex);

    // Perbarui sesi
    session.name = name;
    session.email = email;
    write(SESSION_KEY, session);

    renderHeader(session);
    form.elements.password.value = '';
    notify('success', 'Profil berhasil diperbarui.');
  });
})();
(async () => {
  'use strict';

  const form = document.getElementById('profileForm');
  const pwForm = document.getElementById('passwordForm');

  const notifier = box => (type, text) => {
    box.innerHTML = '';
    if (!text) return;
    const el = document.createElement('div');
    el.className = `alert alert-${type}`;
    el.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    el.textContent = text;           // textContent: tidak ada HTML dari server yang dieksekusi (anti-XSS)
    box.appendChild(el);
  };
  const notify = notifier(document.getElementById('profileAlert'));
  const notifyPw = notifier(document.getElementById('passwordAlert'));

  /* ----- Wajib login (server juga menolak tanpa sesi) ----- */
  let user;
  try { user = await api.me(); }
  catch (e) { return notify('danger', e.message); }
  if (!user) { window.location.replace('login.html?next=profil.html'); return; }

  const render = u => {
    document.getElementById('userName').textContent = `Halo, ${u.name}`;
    document.getElementById('avatar').textContent = u.name.charAt(0).toUpperCase();
    document.getElementById('profilName').textContent = u.name;
    document.getElementById('profilEmail').textContent = u.email;
    form.elements.name.value = u.name;
    form.elements.email.value = u.email;
    form.elements.city.value = u.city || '';
    form.elements.address.value = u.address || '';
  };
  render(user);

  document.getElementById('btnKeluar').addEventListener('click', async () => {
    await api.logout();
    window.location.href = 'landing.html';
  });

  document.querySelectorAll('.form-control').forEach(f => f.addEventListener('input', () =>
    f.classList.toggle('is-invalid', f.value !== '' && !f.checkValidity())));

  /* ----- Simpan profil (hanya nama, kota, alamat) ----- */
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const fields = [form.elements.name, form.elements.city, form.elements.address];
    fields.forEach(f => f.classList.toggle('is-invalid', !f.checkValidity()));
    if (fields.some(f => !f.checkValidity())) return notify('danger', 'Lengkapi nama dengan benar.');
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const r = await api.patch('/api/me', {
        name: form.elements.name.value, city: form.elements.city.value, address: form.elements.address.value
      });
      user = r.user;
      render(user);
      notify('success', 'Profil berhasil diperbarui.');
    } catch (err) {
      if (err.status === 401) return window.location.replace('login.html?next=profil.html');
      notify('danger', err.message);
    } finally { btn.disabled = false; }
  });

  /* ----- Ganti kata sandi ----- */
  pwForm.addEventListener('submit', async e => {
    e.preventDefault();
    const { current, next } = pwForm.elements;
    [current, next].forEach(f => f.classList.toggle('is-invalid', !f.checkValidity()));
    if (!pwForm.checkValidity()) return notifyPw('danger', 'Isi kata sandi saat ini dan kata sandi baru (min. 10 karakter).');
    const btn = pwForm.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await api.post('/api/me/password', { current_password: current.value, new_password: next.value });
      pwForm.reset();
      notifyPw('success', 'Kata sandi diganti. Perangkat lain dikeluarkan dari akunmu.');
    } catch (err) {
      if (err.status === 401) return window.location.replace('login.html?next=profil.html');
      notifyPw('danger', err.message);
    } finally { btn.disabled = false; }
  });
})();

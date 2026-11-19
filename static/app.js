(() => {
  'use strict';

  const card    = document.getElementById('card');
  const formIn  = document.getElementById('formSignIn');
  const formUp  = document.getElementById('formSignUp');
  const formOtp = document.getElementById('formOtp');
  const otpCode = document.getElementById('otpCode');
  const otpResend = document.getElementById('otpResend');
  const otpBack = document.getElementById('otpBack');
  const otpInfo = document.getElementById('otpInfo');

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

  const busy = (form, on) => {
    form.querySelectorAll('button[type=submit]').forEach(b => { b.disabled = on; });
  };

  /* ----- Switch Masuk <-> Daftar ----- */
  const setMode = mode => {
    card.classList.remove('otp-active');
    card.classList.toggle('right-active', mode === 'signup');
    notify(formIn); notify(formUp); notify(formOtp);
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

  /* Tujuan setelah masuk: ?next=... atau beranda. Hanya nama file .html di folder yang sama
     (mencegah open redirect; server memeriksa ulang). */
  const nextUrl = () => {
    const n = new URLSearchParams(window.location.search).get('next') || '';
    return /^[a-z0-9_-]+\.html(\?[a-z0-9_=&-]*)?$/i.test(n) ? n : 'landing.html';
  };
  const goNext = () => window.location.replace(nextUrl());

  /* ===================== OTP ===================== */
  let challenge = null;   // token bertanda tangan dari server (bukti sandi sudah benar)
  let purpose = 'login';
  let timer = null;

  const startCountdown = seconds => {
    clearInterval(timer);
    let left = Math.max(0, Math.ceil(seconds));
    const paint = () => {
      otpResend.disabled = left > 0;
      otpResend.textContent = left > 0 ? `Kirim ulang kode (${left}d)` : 'Kirim ulang kode';
    };
    paint();
    if (left <= 0) return;
    timer = setInterval(() => { left -= 1; paint(); if (left <= 0) clearInterval(timer); }, 1000);
  };

  const showOtp = (data, originForm) => {
    challenge = data.challenge;
    purpose = data.purpose;
    otpCode.value = '';
    notify(formOtp);
    otpInfo.textContent = data.message || 'Masukkan kode 6 digit yang kami kirim ke emailmu.';
    card.classList.remove('right-active');
    card.classList.add('otp-active');
    startCountdown(data.resend_after || 60);
    originForm.dataset.last = '1';
    setTimeout(() => otpCode.focus({ preventScroll: true }), 300);
  };

  const backFromOtp = () => {
    challenge = null;
    clearInterval(timer);
    otpCode.value = '';
    card.classList.remove('otp-active');
    formIn.elements.password.value = '';
    formUp.elements.password.value = '';
    setTimeout(() => formIn.querySelector('input')?.focus({ preventScroll: true }), 300);
  };
  otpBack.addEventListener('click', backFromOtp);

  otpCode.addEventListener('input', () => {
    otpCode.value = otpCode.value.replace(/\D/g, '').slice(0, 6);
    otpCode.classList.remove('is-invalid');
  });

  formOtp.addEventListener('submit', async e => {
    e.preventDefault();
    const code = otpCode.value;
    if (!/^\d{6}$/.test(code)) {
      otpCode.classList.add('is-invalid');
      return notify(formOtp, 'danger', 'Masukkan 6 digit kode.');
    }
    busy(formOtp, true);
    try {
      await api.post('/api/auth/verify', { challenge, code });
      notify(formOtp, 'success', 'Berhasil! Mengalihkan…');
      goNext();
    } catch (err) {
      if (err.code === 'session_expired') { notify(formIn, 'danger', err.message); backFromOtp(); }
      else if (err.code === 'rate_limited') notify(formOtp, 'danger', err.message);
      else { otpCode.classList.add('is-invalid'); otpCode.select(); notify(formOtp, 'danger', err.message); }
    } finally { busy(formOtp, false); }
  });

  otpResend.addEventListener('click', async () => {
    otpResend.disabled = true;
    try {
      const r = await api.post('/api/auth/resend', { challenge });
      notify(formOtp, 'success', r.message || 'Kode baru dikirim.');
      startCountdown(r.resend_after || 60);
    } catch (err) {
      if (err.code === 'session_expired') { notify(formIn, 'danger', err.message); backFromOtp(); return; }
      notify(formOtp, 'danger', err.message);
      startCountdown(err.retryAfter || 5);
    }
  });

  /* ===================== Masuk ===================== */
  formIn.addEventListener('submit', async e => {
    e.preventDefault();
    markInvalid(formIn);
    if (!formIn.checkValidity()) return notify(formIn, 'danger', 'Isi email dan kata sandi dengan benar.');

    const { email, password } = formIn.elements;
    busy(formIn, true);
    try {
      const r = await api.post('/api/auth/login', { email: email.value, password: password.value });
      if (r.otp_required) return showOtp(r, formIn);
      goNext();
    } catch (err) {
      notify(formIn, 'danger', err.message);
    } finally { busy(formIn, false); }
  });

  /* ===================== Daftar ===================== */
  formUp.addEventListener('submit', async e => {
    e.preventDefault();
    markInvalid(formUp);
    if (!formUp.checkValidity()) return notify(formUp, 'danger', 'Lengkapi data. Kata sandi minimal 10 karakter.');

    const { name, email, password } = formUp.elements;
    busy(formUp, true);
    try {
      const r = await api.post('/api/auth/register', { name: name.value, email: email.value, password: password.value });
      showOtp(r, formUp);
    } catch (err) {
      notify(formUp, 'danger', err.message);
    } finally { busy(formUp, false); }
  });

  /* ----- Jika sudah login, tidak perlu di halaman ini ----- */
  api.me().then(u => { if (u) goNext(); }).catch(() => { /* server tak terjangkau: biarkan form tampil */ });

  /* Datang dari halaman yang butuh login: beri tahu */
  if (nextUrl().startsWith('distro.html')) notify(formIn, 'info', 'Masuk dulu untuk membaca materi lengkap distro.');
})();

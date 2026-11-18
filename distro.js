(() => {
  'use strict';

  const SESSION_KEY = 'session';
  const read = (key) => { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } };

  /* ----- Wajib login: kalau belum, ke halaman masuk lalu kembali ke sini ----- */
  const session = read(SESSION_KEY);
  if (!session || !session.email) {
    window.location.replace('login.html?next=' + encodeURIComponent('distro.html' + window.location.search));
    return;
  }

  /* ----- Navbar: nama & keluar ----- */
  document.getElementById('userName').textContent = `Halo, ${session.name}`;
  document.getElementById('btnKeluar').addEventListener('click', () => {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* abaikan */ }
    window.location.href = 'landing.html';
  });

  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const app = document.getElementById('app');
  const key = new URLSearchParams(window.location.search).get('d');
  const d = window.DISTRO_DATA && window.DISTRO_DATA[key];

  /* ----- Distro tidak ditemukan ----- */
  if (!d) {
    document.title = 'Distro tidak ditemukan – Tuxpedia';
    app.innerHTML = `<section class="dp-empty"><div class="container"><div class="panel">
      <h1 class="section-title">Distro tidak ditemukan</h1>
      <p class="lead-text">Halaman yang kamu cari belum ada. Pilih salah satu distro populer di beranda.</p>
      <a class="btn btn-main" href="landing.html#about">KEMBALI KE DAFTAR DISTRO</a>
    </div></div></section>`;
    app.hidden = false;
    return;
  }

  document.title = `${d.name} – Tuxpedia`;

  const codeBlock = code => `<div class="code"><pre><code>${esc(code)}</code></pre><button type="button" class="copy-btn" data-copy>Salin</button></div>`;
  const list = (items, cls = '') => `<ul class="list ${cls}">${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>`;
  const kv = rows => `<dl class="kv">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;

  const sections = [
    ['penjelasan', 'Penjelasan'], ['sejarah', 'Sejarah'], ['spesifikasi', 'Spesifikasi'],
    ['instalasi', 'Cara install'], ['kelebihan', 'Kelebihan'], ['perbandingan', 'Dibanding OS lain']
  ];

  const cmp = window.OS_COMPARE;
  const cmpRows = cmp.rows.map((row, i) => `<tr>
      <th scope="row">${esc(row)}</th>
      <td>${esc(cmp.windows[i])}</td>
      <td>${esc(cmp.macos[i])}</td>
      <td class="me">${esc(d.compare[i])}</td>
    </tr>`).join('');

  const others = window.DISTRO_ORDER.filter(k => k !== key).map(k => {
    const o = window.DISTRO_DATA[k];
    return `<a href="distro.html?d=${encodeURIComponent(k)}">${esc(o.name)} <span>${esc(o.tag)}</span></a>`;
  }).join('');

  app.innerHTML = `
  <section class="dp-hero">
    <div class="container">
      <nav class="crumb" aria-label="Jejak halaman">
        <a href="landing.html#beranda">Beranda</a><span aria-hidden="true">›</span>
        <a href="landing.html#about">Distro populer</a><span aria-hidden="true">›</span>
        <b aria-current="page">${esc(d.name)}</b>
      </nav>
      <div class="dp-hero-grid">
        <div>
          <span class="tag">${esc(d.tag)}</span>
          <h1 class="section-title dp-title">${esc(d.name)}</h1>
          <p class="lead-text">${esc(d.tagline)}</p>
          <dl class="facts">${d.facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
          <div class="dp-actions">
            <a class="btn btn-main" href="#instalasi">CARA INSTALL</a>
            <a class="link-arrow" href="${esc(d.link.url)}" target="_blank" rel="noopener noreferrer">Situs resmi ${esc(d.link.label)} <span aria-hidden="true">↗</span></a>
          </div>
        </div>
        <figure class="frame dp-frame"><img src="${esc(d.img)}" alt="${esc(d.alt)}" style="object-position:${esc(d.pos)}"></figure>
      </div>
    </div>
  </section>

  <div class="dp-tabs-wrap"><div class="container">
    <nav class="dp-tabs" aria-label="Isi halaman">
      ${sections.map(([id, label]) => `<a href="#${id}" data-tab="${id}">${esc(label)}</a>`).join('')}
    </nav>
  </div></div>

  <section class="dp-sec" id="penjelasan"><div class="container"><div class="panel">
    <h2 class="section-title">Apa itu ${esc(d.name)}?</h2>
    <div class="dp-cols">
      <div>${d.about.map(p => `<p>${esc(p)}</p>`).join('')}</div>
      <aside>
        <div class="side-box"><h3>Cocok untuk</h3>${list(d.suited)}</div>
        <div class="side-box"><h3>Kurang cocok untuk</h3>${list(d.notSuited, 'minus')}</div>
        <p class="fun"><strong>Tahukah kamu?</strong> ${esc(d.fun)}</p>
      </aside>
    </div>
  </div></div></section>

  <section class="dp-sec" id="sejarah"><div class="container"><div class="panel">
    <h2 class="section-title">Sejarah ${esc(d.name)}</h2>
    <p class="sub">Perjalanan singkat dari awal sampai sekarang.</p>
    <ol class="timeline">${d.history.map(h => `<li><div class="yr">${esc(h.y)}</div><p>${esc(h.t)}</p></li>`).join('')}</ol>
  </div></div></section>

  <section class="dp-sec" id="spesifikasi"><div class="container"><div class="panel">
    <h2 class="section-title">Spesifikasi</h2>
    <p class="sub">Kebutuhan perangkat dan fakta teknis ${esc(d.name)}.</p>
    <div class="spec-cols">
      <div class="spec-card"><h3>Minimum</h3>${kv(d.specs.min)}</div>
      <div class="spec-card rec"><h3>Disarankan</h3>${kv(d.specs.rec)}</div>
    </div>
    <dl class="tech">${d.specs.tech.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    <p class="spec-note">${esc(d.specs.note)}</p>
  </div></div></section>

  <section class="dp-sec" id="instalasi"><div class="container"><div class="panel">
    <h2 class="section-title">Cara install ${esc(d.name)}</h2>
    <p class="sub">${esc(d.install.intro)}</p>
    <ol class="steps">${d.install.steps.map(s => `<li><h3>${esc(s.t)}</h3><p>${esc(s.d)}</p>${s.code ? codeBlock(s.code) : ''}</li>`).join('')}</ol>
    <div class="after"><h3>${esc(d.install.after.t)}</h3>${codeBlock(d.install.after.code)}</div>
    <div class="note"><h3>Tips</h3>${list(d.install.tips)}</div>
  </div></div></section>

  <section class="dp-sec" id="kelebihan"><div class="container"><div class="panel">
    <h2 class="section-title">Kelebihan ${esc(d.name)}</h2>
    <p class="sub">Alasan orang memilih ${esc(d.name)}, dan hal yang perlu kamu ketahui sebelum mencoba.</p>
    <div class="pros">${d.pros.map(p => `<div class="feat"><h3>${esc(p.t)}</h3><p>${esc(p.d)}</p></div>`).join('')}</div>
    <div class="note"><h3>Perlu kamu ketahui</h3>${list(d.cons, 'warn')}</div>
  </div></div></section>

  <section class="dp-sec" id="perbandingan"><div class="container"><div class="panel">
    <h2 class="section-title">${esc(d.name)} dibanding OS lain</h2>
    <p class="sub">Perbandingan singkat dengan Windows dan macOS dari sisi yang paling sering ditanyakan.</p>
    <div class="cmp-wrap"><table class="cmp">
      <thead><tr><th scope="col"></th><th scope="col">Windows</th><th scope="col">macOS</th><th scope="col" class="me">${esc(d.name)}</th></tr></thead>
      <tbody>${cmpRows}</tbody>
    </table></div>
  </div></div></section>

  <section class="dp-sec"><div class="container">
    <h2 class="section-title">Jelajahi distro lain</h2>
    <div class="others">${others}</div>
  </div></section>`;

  app.hidden = false;

  /* ----- Tombol salin pada blok kode ----- */
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const text = btn.previousElementSibling.textContent;
    const done = () => { btn.textContent = 'Tersalin ✓'; setTimeout(() => { btn.textContent = 'Salin'; }, 1600); };
    const fallback = () => {
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); } catch { /* abaikan */ }
      ta.remove(); done();
    };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, fallback);
    else fallback();
  });

  /* ----- Tab aktif mengikuti posisi gulir ----- */
  const tabs = [...document.querySelectorAll('[data-tab]')];
  const setActive = id => tabs.forEach(a => {
    const on = a.dataset.tab === id;
    a.classList.toggle('active', on);
    if (on) { a.setAttribute('aria-current', 'true'); a.scrollIntoView({ block: 'nearest', inline: 'center' }); }
    else a.removeAttribute('aria-current');
  });
  const spy = new IntersectionObserver(entries => {
    entries.forEach(en => { if (en.isIntersecting) setActive(en.target.id); });
  }, { rootMargin: '-30% 0px -60% 0px' });
  sections.forEach(([id]) => spy.observe(document.getElementById(id)));

  /* ----- Buka dari tautan dengan #bagian ----- */
  if (window.location.hash) {
    const el = document.getElementById(window.location.hash.slice(1));
    if (el) setTimeout(() => el.scrollIntoView(), 50);
  }
})();
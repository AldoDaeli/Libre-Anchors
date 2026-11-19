/* Klien API Tuxpedia: fetch + token CSRF. Tidak menyimpan apa pun di localStorage (sesi = cookie HttpOnly). */
(() => {
  'use strict';

  let csrf = null;

  const loadCsrf = async () => {
    const r = await fetch('/api/csrf', { credentials: 'same-origin', cache: 'no-store' });
    csrf = (await r.json()).token;
  };

  class ApiError extends Error {
    constructor(status, data) {
      super((data && data.message) || 'Terjadi kesalahan.');
      this.status = status;
      this.code = (data && data.error) || 'error';
      this.retryAfter = data && data.retry_after ? Number(data.retry_after) : 0;
    }
  }

  const request = async (method, url, payload, retried = false) => {
    const opts = { method, credentials: 'same-origin', headers: {}, cache: 'no-store' };
    if (method !== 'GET') {
      if (!csrf) await loadCsrf();
      opts.headers['Content-Type'] = 'application/json';
      opts.headers['X-CSRF-Token'] = csrf;
      opts.body = JSON.stringify(payload || {});
    }
    let res;
    try { res = await fetch(url, opts); }
    catch { throw new ApiError(0, { error: 'network', message: 'Tidak bisa terhubung ke server. Periksa koneksi internetmu.' }); }

    let data = null;
    try { data = await res.json(); } catch { /* bukan JSON */ }

    if (res.status === 403 && data && data.error === 'csrf' && !retried) {
      await loadCsrf();                       // token kedaluwarsa: ambil baru, ulangi sekali
      return request(method, url, payload, true);
    }
    if (!res.ok) {
      const retryHeader = Number(res.headers.get('Retry-After')) || 0;
      throw new ApiError(res.status, Object.assign({ retry_after: retryHeader }, data || {}));
    }
    return data;
  };

  window.api = {
    get: url => request('GET', url),
    post: (url, body) => request('POST', url, body),
    patch: (url, body) => request('PATCH', url, body),
    /* Pengguna yang sedang login, atau null bila belum. */
    me: async () => {
      try { return (await request('GET', '/api/me')).user; }
      catch (e) { if (e.status === 401) return null; throw e; }
    },
    logout: async () => { try { await request('POST', '/api/auth/logout'); } catch { /* abaikan */ } }
  };
})();

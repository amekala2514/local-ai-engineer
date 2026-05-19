// Login page script. Extracted from inline <script> in login.html
// so it works with the strict CSP (no 'unsafe-inline' for script-src).

(() => {
  // Pick up theme preference
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || saved === 'light') {
    document.documentElement.dataset.theme = saved;
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.dataset.theme = 'dark';
  }

  const form = document.getElementById('login-form');
  const tokenInput = document.getElementById('token-input');
  const loginButton = document.getElementById('login-button');
  const errorEl = document.getElementById('login-error');

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.hidden = true;
    loginButton.disabled = true;
    loginButton.setAttribute('aria-busy', 'true');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ token: tokenInput.value.trim() }),
      });
      if (res.ok) {
        window.location.href = '/';
        return;
      }
      const data = await res.json().catch(() => ({}));
      errorEl.textContent = data.detail || `Sign-in failed (HTTP ${res.status})`;
      errorEl.hidden = false;
    } catch (e) {
      errorEl.textContent = `Network error: ${e.message}`;
      errorEl.hidden = false;
    } finally {
      loginButton.disabled = false;
      loginButton.removeAttribute('aria-busy');
    }
  });

  tokenInput.focus();
})();

(() => {
  const $ = (sel) => document.querySelector(sel);

  async function api(path, options = {}) {
    const res = await fetch(path, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || data.msg || "Грешка");
    }
    return data;
  }

  function showError(msg) {
    const el = $("#auth-error");
    if (!el) return;
    el.textContent = msg || "";
    el.classList.toggle("hidden", !msg);
  }

  function redirectAfterAuth(user) {
    if (user && user.is_admin) {
      location.href = "/admin";
      return;
    }
    location.href = "/";
  }

  const loginForm = $("#login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("");
      const btn = loginForm.querySelector("button[type=submit]");
      if (btn) btn.disabled = true;
      try {
        const data = await api("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({
            email: $("#email").value,
            password: $("#password").value,
          }),
        });
        redirectAfterAuth(data.user);
      } catch (err) {
        showError(err.message || "Грешка при вход");
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }

  const registerForm = $("#register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      showError("");
      const btn = registerForm.querySelector("button[type=submit]");
      if (btn) btn.disabled = true;
      try {
        const data = await api("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({
            name: ($("#name") && $("#name").value) || "",
            email: $("#email").value,
            password: $("#password").value,
          }),
        });
        redirectAfterAuth(data.user);
      } catch (err) {
        showError(err.message || "Грешка при регистрация");
      } finally {
        if (btn) btn.disabled = false;
      }
    });
  }
})();

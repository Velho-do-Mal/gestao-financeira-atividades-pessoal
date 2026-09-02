/* static/js/app.js
   Helpers genéricos: modais, toasts, fetch JSON, confirmação de exclusão. */

(function () {
  "use strict";

  // ─── Modais ────────────────────────────────────────────────────
  window.openModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.add("open");
  };

  window.closeModal = function (id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
  };

  document.addEventListener("click", function (e) {
    if (e.target.classList && e.target.classList.contains("modal-overlay")) {
      e.target.classList.remove("open");
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      document.querySelectorAll(".modal-overlay.open").forEach(function (el) {
        el.classList.remove("open");
      });
    }
  });

  // ─── Toasts ────────────────────────────────────────────────────
  window.toast = function (message, type) {
    type = type || "success";
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      el.style.transition = "opacity .3s";
      setTimeout(function () { el.remove(); }, 300);
    }, 3200);
  };

  // ─── Fetch JSON helper ─────────────────────────────────────────
  window.apiRequest = async function (url, options) {
    options = options || {};
    options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.body && typeof options.body !== "string") {
      options.body = JSON.stringify(options.body);
    }
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch (e) { /* sem corpo JSON */ }
    if (!res.ok) {
      const msg = (data && data.error) || ("Erro " + res.status);
      throw new Error(msg);
    }
    return data;
  };

  // ─── Confirmação de exclusão via fetch DELETE ──────────────────
  window.confirmDelete = function (message, url, onSuccess) {
    if (!window.confirm(message || "Tem certeza que deseja excluir?")) return;
    apiRequest(url, { method: "DELETE" })
      .then(function () {
        toast("Excluído com sucesso.");
        if (onSuccess) onSuccess();
        else window.location.reload();
      })
      .catch(function (err) { toast(err.message, "error"); });
  };

  // ─── Menu hambúrguer (mobile) ───────────────────────────────────
  window.toggleMobileMenu = function () {
    document.body.classList.toggle("mobile-menu-open");
  };
})();

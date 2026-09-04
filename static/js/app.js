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

  // ─── Tabelas editáveis (estilo planilha) ────────────────────────
  // Qualquer <input>/<select>/<textarea class="sheet-cell"> com
  // data-url="/endpoint" e data-field="coluna" salva sozinho ao sair
  // do campo (change/blur) — sem precisar de botão "Salvar" nem modal.
  // O backend recebe {field, value} em JSON e deve validar o campo
  // contra uma lista de colunas permitidas antes de gravar.
  function _sheetCellValue(el) {
    if (el.type === "checkbox") return el.checked;
    return el.value;
  }

  function _saveSheetCell(el) {
    const url = el.dataset.url;
    const field = el.dataset.field;
    if (!url || !field) return;
    el.classList.remove("sheet-cell--saved", "sheet-cell--error");
    el.classList.add("sheet-cell--saving");
    apiRequest(url, { method: "POST", body: { field: field, value: _sheetCellValue(el) } })
      .then(function () {
        el.classList.remove("sheet-cell--saving");
        el.classList.add("sheet-cell--saved");
        // Campo "parent_id" (hierarquia de Atividades) muda a posição/
        // indentação da linha na árvore — precisa recarregar pra
        // reordenar e mostrar a indentação certa (as outras células só
        // atualizam o próprio valor, sem afetar o layout das outras
        // linhas, então não precisam de reload).
        if (field === "parent_id") {
          window.location.reload();
          return;
        }
        setTimeout(function () { el.classList.remove("sheet-cell--saved"); }, 1200);
      })
      .catch(function (err) {
        el.classList.remove("sheet-cell--saving");
        el.classList.add("sheet-cell--error");
        toast(err.message || "Erro ao salvar", "error");
      });
  }

  document.addEventListener("change", function (e) {
    const el = e.target;
    if (el.classList && el.classList.contains("sheet-cell")) {
      _saveSheetCell(el);
    }
  });

  // Para <input type="text">/número, "change" só dispara ao perder o
  // foco — ok. Para textarea de texto livre, também usamos "blur" para
  // não depender só do evento change do navegador.
  document.addEventListener(
    "blur",
    function (e) {
      const el = e.target;
      if (el.classList && el.classList.contains("sheet-cell") && el.tagName === "TEXTAREA") {
        _saveSheetCell(el);
      }
    },
    true
  );

  // Botão "+ Nova linha": data-url aponta para o endpoint que cria um
  // registro em branco; ao criar, recarrega a página para mostrar a
  // nova linha já editável (mantém o backend simples — sem precisar
  // duplicar a renderização da linha em JS).
  document.addEventListener("click", function (e) {
    const el = e.target.closest && e.target.closest(".sheet-add-row");
    if (!el) return;
    const url = el.dataset.url;
    if (!url) return;
    el.style.opacity = "0.6";
    apiRequest(url, { method: "POST", body: el.dataset.payload ? JSON.parse(el.dataset.payload) : {} })
      .then(function () { window.location.reload(); })
      .catch(function (err) {
        el.style.opacity = "1";
        toast(err.message || "Erro ao adicionar linha", "error");
      });
  });
})();

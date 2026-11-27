// Petits conforts de l'espace connecté. Fichier servi par l'application elle-même (aucun script dans les pages).
(function () {
  "use strict";

  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  // Filtre instantané : tout <table data-filterable> reçoit un champ de recherche au-dessus de lui.
  document.querySelectorAll("table[data-filterable]").forEach(function (table) {
    var rows = Array.prototype.slice.call(table.tBodies[0] ? table.tBodies[0].rows : []);
    if (rows.length < 6) return;                       // inutile pour une petite liste
    var box = document.createElement("div");
    box.className = "table-filter";
    var input = document.createElement("input");
    input.type = "search";
    input.placeholder = table.getAttribute("data-filter-label") || "Filtrer…";
    input.setAttribute("aria-label", input.placeholder);
    var count = document.createElement("span");
    count.className = "muted";
    count.setAttribute("aria-live", "polite");
    box.appendChild(input);
    box.appendChild(count);
    var anchor = table.closest(".table-wrap") || table;
    anchor.parentNode.insertBefore(box, anchor);
    var texts = rows.map(function (r) { return norm(r.textContent); });
    function apply() {
      var q = norm(input.value).trim(), shown = 0;
      rows.forEach(function (r, i) {
        var hit = !q || texts[i].indexOf(q) !== -1;
        r.hidden = !hit;
        if (hit) shown++;
      });
      count.textContent = q ? shown + " / " + rows.length : "";
    }
    input.addEventListener("input", apply);
  });

  // Un tableau plus large que l'écran défile au clavier : la zone devient atteignable avec Tab (accessibilité).
  document.querySelectorAll(".table-wrap").forEach(function (w) {
    if (w.scrollWidth > w.clientWidth) { w.tabIndex = 0; }
  });

  // Page « Accès par rubrique » : cellules colorées, profils en un clic par rôle, compteur de modifications non enregistrées.
  var form = document.getElementById("access-form");
  if (form) {
    var selects = Array.prototype.slice.call(form.querySelectorAll("select.lvl"));
    var bar = document.getElementById("save-bar"), pending = document.getElementById("pending-count");
    var idle = pending ? pending.textContent : "";
    var dirty = false;
    form.querySelectorAll(".js-only").forEach(function (n) { n.hidden = false; });
    function refresh() {
      var changed = 0;
      selects.forEach(function (sel) {
        sel.className = "lvl lv" + sel.value;
        if (sel.value !== sel.dataset.initial) changed++;
        sel.parentNode.classList.toggle("changed", sel.value !== sel.dataset.default);
      });
      dirty = changed > 0;
      if (bar) bar.classList.toggle("dirty", dirty);
      if (pending) pending.textContent = dirty ? changed + " " + (pending.getAttribute("data-label") || "") : idle;
      form.querySelectorAll("[data-count-role]").forEach(function (n) {
        var role = n.getAttribute("data-count-role"), visible = selects.filter(function (s) { return s.dataset.role === role && s.value !== "0"; }).length;
        n.textContent = visible + " / " + selects.filter(function (s) { return s.dataset.role === role; }).length;
      });
    }
    form.addEventListener("change", refresh);
    form.querySelectorAll("[data-preset]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var role = btn.dataset.role;
        selects.forEach(function (sel) {
          if (sel.dataset.role !== role) return;
          sel.value = btn.dataset.preset === "default" ? sel.dataset.default : btn.dataset.preset;
        });
        refresh();
      });
    });
    form.addEventListener("submit", function () { dirty = false; });
    window.addEventListener("beforeunload", function (e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
    refresh();
  }

  // Raccourci « / » : place le curseur dans la recherche globale.
  var global = document.getElementById("global-search");
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || !global) return;
    var t = e.target && e.target.tagName;
    if (t === "INPUT" || t === "TEXTAREA" || t === "SELECT") return;
    e.preventDefault();
    global.focus();
  });

  // Un menu déroulant marqué data-autosubmit envoie son formulaire dès qu'on change la valeur (année, filtre…).
  document.querySelectorAll("select[data-autosubmit]").forEach(function (sel) {
    sel.addEventListener("change", function () { if (sel.form) sel.form.submit(); });
  });
})();

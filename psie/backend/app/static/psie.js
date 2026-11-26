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

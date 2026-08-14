var API_BASE = window.LECIM_API_BASE || "http://localhost:8000";

document.addEventListener("DOMContentLoaded", function () {
  initNavToggle();
  initLoginLink();
  initContactForm();
  initAdhesionForm();
  loadNews();
  loadActivities();
  loadPublications();
  loadHistorique();
  loadGouvernance();
  loadSiteContent();
  loadCarte();
  loadResultatsExamens();
  loadEcoles();
  loadHeroStats();
  loadPartenaires();
  loadInitiatives();
});

function loadHeroStats() {
  var ecolesEl = document.getElementById("hero-stat-ecoles");
  var regionsEl = document.getElementById("hero-stat-regions");
  var enseignantsEl = document.getElementById("hero-stat-enseignants");
  var elevesEl = document.getElementById("hero-stat-eleves");
  if (!ecolesEl && !regionsEl && !enseignantsEl && !elevesEl) return;

  fetch(API_BASE + "/api/etablissements/stats")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (stats) {
      if (!stats) return;
      if (ecolesEl && stats.ecoles) ecolesEl.textContent = stats.ecoles + "+";
      if (regionsEl && stats.regions) regionsEl.textContent = stats.regions + "+";
      if (enseignantsEl && stats.enseignants) enseignantsEl.textContent = stats.enseignants + "+";
      if (elevesEl && stats.eleves) elevesEl.textContent = stats.eleves.toLocaleString("fr-FR") + "+";
    })
    .catch(function () {
      // API indisponible : les chiffres par défaut codés dans la page restent affichés.
    });
}

function loadPartenaires() {
  var section = document.getElementById("partenaires-section");
  var container = document.getElementById("partenaires-list");
  if (!section || !container) return;

  fetch(API_BASE + "/api/partenaires")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = items
        .map(function (p) {
          return '<div class="partenaire-chip">' + p.nom + "</div>";
        })
        .join("");
      section.style.display = "";
    })
    .catch(function () {
      // API indisponible ou aucun partenaire publié : la section reste masquée.
    });
}

function loadSiteContent() {
  var elements = document.querySelectorAll("[data-content-key]");
  if (!elements.length) return;

  fetch(API_BASE + "/api/site-content")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (values) {
      elements.forEach(function (el) {
        var value = values[el.getAttribute("data-content-key")];
        if (value) el.textContent = value;
      });
    })
    .catch(function () {
      // API indisponible : les textes par défaut codés dans la page restent affichés.
    });
}

function loadCarte() {
  var container = document.getElementById("carte-lecim");
  if (!container || typeof L === "undefined") return;

  var map = L.map(container).setView([7.54, -5.55], 7); // Centre approximatif de la Côte d'Ivoire
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; contributeurs OpenStreetMap",
    maxZoom: 18,
  }).addTo(map);

  fetch(API_BASE + "/api/carte")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (markers) {
      if (!markers || !markers.length) {
        document.getElementById("carte-empty").style.display = "block";
        return;
      }
      var bounds = [];
      markers.forEach(function (m) {
        var color = m.type === "delegation" ? "#e0a52c" : "#0f7a4c";
        var icon = L.divIcon({
          className: "",
          html: '<div style="width:16px;height:16px;border-radius:50%;background:' + color + ';border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4);"></div>',
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        });
        var label = m.type === "delegation" ? "Délégation régionale" : "Établissement affilié";
        var popup = "<strong>" + escapeHtml(m.nom) + "</strong><br>" + label + (m.detail ? "<br>" + escapeHtml(m.detail) : "");
        L.marker([m.latitude, m.longitude], { icon: icon }).addTo(map).bindPopup(popup);
        bounds.push([m.latitude, m.longitude]);
      });
      if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 10 });
    })
    .catch(function () {
      document.getElementById("carte-empty").style.display = "block";
    });
}

function loadEcoles() {
  var list = document.getElementById("ecoles-list");
  if (!list) return;

  var regionsNav = document.getElementById("ecoles-regions-nav");
  var countEl = document.getElementById("ecoles-count-num");
  var emptyEl = document.getElementById("ecoles-empty");
  var searchInput = document.getElementById("ecoles-search-input");

  fetch(API_BASE + "/api/etablissements")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (ecoles) {
      if (!ecoles || !ecoles.length) {
        emptyEl.style.display = "block";
        return;
      }

      var groups = {};
      ecoles.forEach(function (e) {
        var region = (e.bureau_local || "").trim() || "Non précisé";
        if (!groups[region]) groups[region] = [];
        groups[region].push(e);
      });
      var regionNames = Object.keys(groups).sort(function (a, b) {
        if (a === "Non précisé") return 1;
        if (b === "Non précisé") return -1;
        return a.localeCompare(b, "fr");
      });

      var slug = function (s) {
        return "region-" + s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-");
      };

      var navHtml = "";
      regionNames.forEach(function (region) {
        navHtml += '<a href="#' + slug(region) + '">' + escapeHtml(region) + " (" + groups[region].length + ")</a>";
      });
      regionsNav.innerHTML = navHtml;

      var niveauLabels = { primaire: "Primaire", secondaire: "Secondaire", les_deux: "Primaire & secondaire" };

      var listHtml = "";
      regionNames.forEach(function (region) {
        var items = groups[region];
        listHtml += '<div class="ecole-region" id="' + slug(region) + '" data-region="' + escapeHtml(region.toLowerCase()) + '">';
        listHtml += "<h2>" + escapeHtml(region) + ' <span class="count">' + items.length + "</span></h2>";
        listHtml += '<div class="ecole-grid">';
        items.forEach(function (e) {
          var logo = e.logo_url ? API_BASE + e.logo_url : "assets/img/logo.jpg";
          var niveau = niveauLabels[e.type_enseignement] || "";
          listHtml += '<div class="ecole-card" data-nom="' + escapeHtml(e.nom.toLowerCase()) + '">';
          listHtml += '<img src="' + logo + '" alt="" loading="lazy" onerror="this.src=\'assets/img/logo.jpg\'">';
          listHtml += '<div class="ecole-card-body"><h3>' + escapeHtml(e.nom) + "</h3>";
          if (niveau) listHtml += '<span class="niveau">' + niveau + "</span>";
          if (e.numero_agrement) listHtml += '<span class="agrement-badge">Agréée</span>';
          listHtml += "</div></div>";
        });
        listHtml += "</div></div>";
      });
      list.innerHTML = listHtml;
      countEl.textContent = ecoles.length;

      if (searchInput) {
        searchInput.addEventListener("input", function () {
          var term = searchInput.value.trim().toLowerCase();
          var visibleTotal = 0;
          document.querySelectorAll(".ecole-region").forEach(function (regionEl) {
            var regionMatches = regionEl.getAttribute("data-region").indexOf(term) !== -1;
            var visibleInRegion = 0;
            regionEl.querySelectorAll(".ecole-card").forEach(function (card) {
              var match = regionMatches || card.getAttribute("data-nom").indexOf(term) !== -1;
              card.style.display = match ? "" : "none";
              if (match) visibleInRegion++;
            });
            regionEl.style.display = visibleInRegion ? "" : "none";
            visibleTotal += visibleInRegion;
          });
          countEl.textContent = visibleTotal;
          emptyEl.style.display = visibleTotal ? "none" : "block";
        });
      }
    })
    .catch(function () {
      emptyEl.style.display = "block";
    });
}

function loadResultatsExamens() {
  var tbody = document.getElementById("resultats-tbody");
  if (!tbody) return;

  fetch(API_BASE + "/api/resultats-examens")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        document.getElementById("resultats-empty").style.display = "block";
        return;
      }

      var select = document.getElementById("resultats-filtre-annee");
      var annees = [];
      items.forEach(function (r) {
        if (annees.indexOf(r.annee_scolaire) === -1) annees.push(r.annee_scolaire);
      });
      annees.forEach(function (annee) {
        var opt = document.createElement("option");
        opt.value = annee;
        opt.textContent = annee;
        select.appendChild(opt);
      });

      function render() {
        var filtre = select.value;
        tbody.innerHTML = "";
        items
          .filter(function (r) { return !filtre || r.annee_scolaire === filtre; })
          .forEach(function (r) {
            var tr = document.createElement("tr");
            tr.innerHTML =
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.etablissement_nom) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.annee_scolaire) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.type_examen) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.nombre_inscrits + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.nombre_admis + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right; font-weight:700; color:var(--green-dark);">' + r.taux_reussite + "%</td>";
            tbody.appendChild(tr);
          });
      }

      select.addEventListener("change", render);
      render();
    })
    .catch(function () {
      document.getElementById("resultats-empty").style.display = "block";
    });
}

function initLoginLink() {
  var link = document.getElementById("nav-login-link");
  if (link) {
    link.href = API_BASE + "/admin/login";
  }
}

function initNavToggle() {
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      links.classList.toggle("open");
    });
  }
}

function initContactForm() {
  var form = document.querySelector(".contact-form form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var payload = {
      full_name: valueOf(form, "#nom"),
      phone: valueOf(form, "#tel") || null,
      email: valueOf(form, "#email"),
      establishment: valueOf(form, "#etablissement") || null,
      subject: valueOf(form, "#sujet"),
      message: valueOf(form, "#message"),
    };

    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    fetch(API_BASE + "/api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Échec de l'envoi");
        btn.textContent = "Message envoyé ✓";
        form.reset();
      })
      .catch(function () {
        btn.textContent = "Erreur — merci de réessayer";
      })
      .finally(function () {
        setTimeout(function () {
          btn.textContent = original;
          btn.disabled = false;
        }, 3500);
      });
  });
}

function initAdhesionForm() {
  var form = document.getElementById("adhesion-form");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var effectif = valueOf(form, "#ad-effectif");
    var payload = {
      nom_etablissement: valueOf(form, "#ad-nom-etablissement"),
      nom_directeur: valueOf(form, "#ad-nom-directeur"),
      telephone: valueOf(form, "#ad-tel"),
      email: valueOf(form, "#ad-email") || null,
      localite: valueOf(form, "#ad-localite"),
      type_enseignement: valueOf(form, "#ad-type"),
      effectif_estime: effectif ? parseInt(effectif, 10) : null,
      message: valueOf(form, "#ad-message") || null,
    };

    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    fetch(API_BASE + "/api/adhesion-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Échec de l'envoi");
        btn.textContent = "Demande envoyée ✓";
        form.reset();
      })
      .catch(function () {
        btn.textContent = "Erreur — merci de réessayer";
      })
      .finally(function () {
        setTimeout(function () {
          btn.textContent = original;
          btn.disabled = false;
        }, 3500);
      });
  });
}

function loadInitiatives() {
  var container = document.getElementById("initiatives-list");
  var emptyEl = document.getElementById("initiatives-empty");
  if (!container) return;

  fetch(API_BASE + "/api/projets")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      if (emptyEl) emptyEl.style.display = "none";
      container.innerHTML = items
        .map(function (p) {
          return (
            '<div class="initiative-card"><span class="initiative-statut">' +
            escapeHtml(p.statut_label) +
            "</span><h3>" +
            escapeHtml(p.titre) +
            "</h3>" +
            (p.description ? "<p>" + escapeHtml(p.description) + "</p>" : "") +
            "</div>"
          );
        })
        .join("");
    })
    .catch(function () {
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function valueOf(form, selector) {
  var el = form.querySelector(selector);
  return el ? el.value.trim() : "";
}

function loadNews() {
  var container = document.querySelector(".news-list");
  if (!container) return;

  fetch(API_BASE + "/api/news?limit=3")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = "";
      items.forEach(function (item, index) {
        var reverse = index % 2 === 1;
        var el = document.createElement("div");
        el.className = "news-item" + (reverse ? " reverse" : "");
        var media = item.image_url
          ? '<img src="' + API_BASE + item.image_url + '" alt="' + escapeHtml(item.title) + '">'
          : '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5"/></svg>';
        el.innerHTML =
          '<div class="news-media">' + media + "</div>" +
          "<div>" +
          '<span class="news-date">' + formatDateFr(item.published_at) + "</span>" +
          "<h3>" + escapeHtml(item.title) + "</h3>" +
          "<p>" + escapeHtml(item.excerpt) + "</p>" +
          "</div>";
        container.appendChild(el);
      });
    })
    .catch(function () {
      // API indisponible (ex. ouverture locale du fichier) : le contenu statique reste affiché.
    });
}

function loadActivities() {
  var container = document.querySelector(".timeline");
  if (!container) return;

  fetch(API_BASE + "/api/activities")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = "";
      items.forEach(function (item) {
        var isPast = item.status === "past";
        var el = document.createElement("div");
        el.className = "timeline-item" + (isPast ? " past" : "");
        el.innerHTML =
          '<div class="timeline-dot"></div>' +
          '<div class="timeline-card">' +
          '<span class="timeline-tag">' + (isPast ? "Terminé" : "À venir") + "</span>" +
          '<div class="tdate">' + formatDateFr(item.event_date) + "</div>" +
          "<h3>" + escapeHtml(item.title) + "</h3>" +
          "<p>" + escapeHtml(item.description) + "</p>" +
          "</div>";
        container.appendChild(el);
      });
    })
    .catch(function () {
      // API indisponible : le contenu statique reste affiché.
    });
}

var PUBLICATION_CATEGORY_LABELS = {
  reglement_interieur: "Règlement Intérieur",
  statuts: "Statuts de la LECIM",
  resultats_examens: "Résultats aux examens nationaux",
  autre: "Autres documents",
};
var PUBLICATION_CATEGORY_ORDER = ["reglement_interieur", "statuts", "resultats_examens", "autre"];

function loadPublications() {
  var container = document.getElementById("doc-categories");
  if (!container) return;

  fetch(API_BASE + "/api/publications")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;

      var byCategory = {};
      items.forEach(function (item) {
        var cat = item.category || "autre";
        if (!byCategory[cat]) byCategory[cat] = [];
        byCategory[cat].push(item);
      });

      container.innerHTML = "";
      PUBLICATION_CATEGORY_ORDER.forEach(function (cat) {
        var docs = byCategory[cat];
        if (!docs || !docs.length) return;

        var section = document.createElement("div");
        section.className = "doc-category";

        var heading = document.createElement("h2");
        heading.textContent = PUBLICATION_CATEGORY_LABELS[cat] || cat;
        section.appendChild(heading);

        var grid = document.createElement("div");
        grid.className = "doc-grid";

        docs.forEach(function (doc) {
          var card = document.createElement("div");
          card.className = "doc-card";
          card.innerHTML =
            '<div class="doc-icon"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.5">' +
            '<path d="M4 19V6a2 2 0 0 1 2-2h9l5 5v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"/><path d="M14 4v5h5"/></svg></div>' +
            "<div>" +
            "<h3>" + escapeHtml(doc.title) + "</h3>" +
            (doc.description ? "<p>" + escapeHtml(doc.description) + "</p>" : "") +
            '<div class="doc-meta">Publié le ' + formatDateFr(doc.published_at) + "</div>" +
            '<a href="' + API_BASE + doc.file_url + '" class="btn btn-primary" target="_blank">Télécharger</a>' +
            "</div>";
          grid.appendChild(card);
        });

        section.appendChild(grid);
        container.appendChild(section);
      });
    })
    .catch(function () {
      // API indisponible : le message par défaut ("aucun document") reste affiché.
    });
}

function loadHistorique() {
  var container = document.getElementById("historique-grid");
  if (!container) return;

  fetch(API_BASE + "/api/historique")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = "";
      items.forEach(function (item) {
        var card = document.createElement("div");
        card.className = "historique-card";
        card.innerHTML =
          '<img class="historique-photo" src="' + API_BASE + item.photo_url + '" alt="' + escapeHtml(item.full_name) + '">' +
          "<h4>" + escapeHtml(item.full_name) + "</h4>" +
          (item.periode ? '<span class="historique-period">' + escapeHtml(item.periode) + "</span>" : "") +
          (item.mot ? '<p class="historique-mot">' + escapeHtml(item.mot) + "</p>" : "");
        container.appendChild(card);
      });
    })
    .catch(function () {
      // API indisponible : le message par défaut ("aucun ancien président") reste affiché.
    });
}

function initialsFrom(text) {
  if (!text) return "?";
  var words = text.split(/\s+/).filter(function (w) { return w.length > 1; });
  var letters = words.slice(0, 2).map(function (w) { return w.charAt(0).toUpperCase(); });
  return letters.join("") || text.charAt(0).toUpperCase();
}

function loadGouvernance() {
  var container = document.getElementById("gouvernance-grid");
  if (!container) return;

  fetch(API_BASE + "/api/gouvernance")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = "";
      items.forEach(function (item) {
        var card = document.createElement("div");
        card.className = "org-card";

        var titulaireInner = item.titulaire_photo_url
          ? '<img src="' + API_BASE + item.titulaire_photo_url + '" alt="' + escapeHtml(item.titulaire_nom || item.poste_title) + '">'
          : initialsFrom(item.titulaire_nom || item.poste_title);

        var adjointBadge = "";
        if (item.adjoint_nom || item.adjoint_photo_url) {
          var adjointInner = item.adjoint_photo_url
            ? '<img src="' + API_BASE + item.adjoint_photo_url + '" alt="' + escapeHtml(item.adjoint_nom || "") + '">'
            : initialsFrom(item.adjoint_nom);
          adjointBadge = '<div class="org-adjoint-badge" title="Adjoint' + (item.adjoint_nom ? " : " + escapeHtml(item.adjoint_nom) : "") + '">' + adjointInner + "</div>";
        }

        card.innerHTML =
          '<div class="org-avatar-wrap">' +
          '<div class="org-avatar">' + titulaireInner + "</div>" +
          adjointBadge +
          "</div>" +
          "<h4>" + escapeHtml(item.titulaire_nom || item.poste_title) + "</h4>" +
          '<span>' + escapeHtml(item.poste_subtitle || item.poste_title) + "</span>";
        container.appendChild(card);
      });
    })
    .catch(function () {
      // API indisponible : l'organigramme statique par défaut reste affiché.
    });
}

function formatDateFr(isoDate) {
  try {
    var d = new Date(isoDate + "T00:00:00");
    return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
  } catch (e) {
    return isoDate;
  }
}

function escapeHtml(value) {
  var div = document.createElement("div");
  div.textContent = value == null ? "" : value;
  return div.innerHTML;
}

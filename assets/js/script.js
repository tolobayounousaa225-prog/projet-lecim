var API_BASE = window.LECIM_API_BASE || "http://localhost:8000";

document.addEventListener("DOMContentLoaded", function () {
  initNavToggle();
  initLoginLink();
  initContactForm();
  initAdhesionForm();
  initPartenariatForm();
  initDonForm();
  initGlobalSearch();
  loadNews();
  loadActivities();
  loadPublications();
  loadHistorique();
  loadFondateurs();
  loadGouvernance();
  loadSiteContent();
  loadCarte();
  loadResultatsExamens();
  loadEcoles();
  loadHeroStats();
  loadPartenaires();
  loadInitiatives();
  loadActualitesFull();
  loadActualiteDetail();
  loadGalerie();
  loadFaq();
  loadTransparence();
  loadUpcomingEvents();
  initPushNotifications();
  loadBaremetre();
});

function urlBase64ToUint8Array(base64String) {
  var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  var rawData = atob(base64);
  var outputArray = new Uint8Array(rawData.length);
  for (var i = 0; i < rawData.length; i++) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

function initPushNotifications() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  if (!("Notification" in window) || Notification.permission === "denied") return;
  if (localStorage.getItem("lecim_push_dismissed") === "1") return;
  if (Notification.permission === "granted") return;

  var banner = document.getElementById("push-banner");
  if (!banner) return;

  fetch(API_BASE + "/api/push/public-key")
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (!data || !data.publicKey) return;

      var acceptBtn = document.getElementById("push-banner-accept");
      var dismissBtn = document.getElementById("push-banner-dismiss");
      banner.style.display = "flex";

      dismissBtn.addEventListener("click", function () {
        localStorage.setItem("lecim_push_dismissed", "1");
        banner.style.display = "none";
      });

      acceptBtn.addEventListener("click", function () {
        Notification.requestPermission().then(function (permission) {
          banner.style.display = "none";
          if (permission !== "granted") return;
          navigator.serviceWorker.ready.then(function (registration) {
            registration.pushManager
              .subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(data.publicKey),
              })
              .then(function (subscription) {
                var json = subscription.toJSON();
                fetch(API_BASE + "/api/push/subscribe", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    endpoint: json.endpoint,
                    keys: json.keys,
                    lang: document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr",
                  }),
                }).catch(function () {});
              })
              .catch(function () {});
          });
        });
      });
    })
    .catch(function () {});
}

function loadHeroStats() {
  var ecolesEl = document.getElementById("hero-stat-ecoles");
  var regionsEl = document.getElementById("hero-stat-regions");
  var enseignantsEl = document.getElementById("hero-stat-enseignants");
  var elevesEl = document.getElementById("hero-stat-eleves");
  var badgeEcolesEl = document.getElementById("hero-badge-ecoles");
  var badgeRegionsEl = document.getElementById("hero-badge-regions");
  if (!ecolesEl && !regionsEl && !enseignantsEl && !elevesEl && !badgeEcolesEl && !badgeRegionsEl) return;

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
      if (badgeEcolesEl && stats.ecoles) badgeEcolesEl.textContent = stats.ecoles + "+";
      if (badgeRegionsEl && stats.regions) badgeRegionsEl.textContent = stats.regions + "+";
    })
    .catch(function () {
      // API indisponible : les chiffres par défaut codés dans la page restent affichés.
    });
}

function loadPartenaires() {
  var section = document.getElementById("partenaires-section");
  var track = document.getElementById("partenaires-track");
  if (!section || !track) return;

  fetch(API_BASE + "/api/partenaires")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      var itemsHtml = items
        .map(function (p) {
          if (p.logo_url) {
            return '<img class="partenaires-logo" src="' + API_BASE + p.logo_url + '" alt="' + escapeHtml(p.nom) + '" loading="lazy">';
          }
          return '<div class="partenaire-chip">' + escapeHtml(p.nom) + "</div>";
        })
        .join("");
      // Le contenu est dupliqué pour permettre un défilement continu sans coupure.
      track.innerHTML = itemsHtml + itemsHtml;
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
          listHtml += '<div class="ecole-card" id="ecole-' + e.id + '" data-nom="' + escapeHtml(e.nom.toLowerCase()) + '">';
          listHtml += '<img src="' + logo + '" alt="" loading="lazy" onerror="this.src=\'assets/img/logo.jpg\'">';
          listHtml += '<div class="ecole-card-body"><h3>' + escapeHtml(e.nom) + "</h3>";
          if (niveau) listHtml += '<span class="niveau">' + niveau + "</span>";
          if (e.statut_agrement_label) {
            listHtml += '<span class="agrement-badge ' + escapeHtml(e.statut_agrement || "") + '">' + escapeHtml(e.statut_agrement_label) + "</span>";
          }
          if (e.is_ecole_modele) {
            listHtml += '<span class="ecole-modele-badge"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m12 2 2.9 6.3 6.9.8-5.1 4.6 1.5 6.8L12 17l-6.2 3.5 1.5-6.8-5.1-4.6 6.9-.8Z"/></svg>École modèle</span>';
          }
          listHtml += "</div></div>";
        });
        listHtml += "</div></div>";
      });
      list.innerHTML = listHtml;
      countEl.textContent = ecoles.length;
      if (location.hash) {
        var target = document.querySelector(location.hash);
        if (target && target.classList.contains("ecole-card")) scrollToHighlight(target);
      }

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

function tauxPillClass(taux) {
  if (taux >= 70) return "good";
  if (taux >= 50) return "mid";
  return "low";
}

function loadBaremetre() {
  var nationalBody = document.getElementById("baremetre-national-tbody");
  var regionalBody = document.getElementById("baremetre-regional-tbody");
  var emptyEl = document.getElementById("baremetre-empty");
  if (!nationalBody && !regionalBody) return;

  fetch(API_BASE + "/api/resultats-examens/baremetre")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (data) {
      if (!data || (!data.national.length && !data.regional.length)) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }

      if (nationalBody) {
        nationalBody.innerHTML = data.national
          .map(function (r) {
            return (
              "<tr>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.annee_scolaire) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.type_examen) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.inscrits + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.admis + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;"><span class="taux-pill ' + tauxPillClass(r.taux_reussite) + '">' + r.taux_reussite + "%</span></td>" +
              "</tr>"
            );
          })
          .join("");
      }

      if (regionalBody) {
        regionalBody.innerHTML = data.regional
          .map(function (r) {
            return (
              "<tr>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.annee_scolaire) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border);">' + escapeHtml(r.bureau_local) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.inscrits + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + r.admis + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;"><span class="taux-pill ' + tauxPillClass(r.taux_reussite) + '">' + r.taux_reussite + "%</span></td>" +
              "</tr>"
            );
          })
          .join("");
      }
    })
    .catch(function () {
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function initLoginLink() {
  var link = document.getElementById("nav-login-link");
  if (link) {
    link.href = API_BASE + "/admin/login";
  }
}

var SEARCH_STATIC_PAGES = {
  fr: [
    { title: "Accueil", url: "index.html" },
    { title: "À propos", url: "apropos.html" },
    { title: "Services", url: "services.html" },
    { title: "Activités", url: "activites.html" },
    { title: "Établissements affiliés", url: "ecoles.html" },
    { title: "Carte interactive", url: "carte.html" },
    { title: "Documents", url: "documents.html" },
    { title: "Initiatives", url: "initiatives.html" },
    { title: "Actualités", url: "actualites.html" },
    { title: "Galerie photo", url: "galerie.html" },
    { title: "FAQ", url: "faq.html" },
    { title: "Transparence financière", url: "transparence.html" },
    { title: "Baromètre des résultats", url: "baremetre.html" },
    { title: "Adhésion", url: "adhesion.html" },
    { title: "Devenir partenaire", url: "partenariat.html" },
    { title: "Faire un don", url: "don.html" },
    { title: "Contact", url: "contact.html" }
  ],
  ar: [
    { title: "الرئيسية", url: "index.html" },
    { title: "من نحن", url: "apropos.html" },
    { title: "خدماتنا", url: "services.html" },
    { title: "أنشطتنا", url: "activites.html" },
    { title: "مدارسنا", url: "ecoles.html" },
    { title: "الخريطة", url: "carte.html" },
    { title: "الوثائق", url: "documents.html" },
    { title: "مبادراتنا", url: "initiatives.html" },
    { title: "الأخبار", url: "actualites.html" },
    { title: "معرض الصور", url: "galerie.html" },
    { title: "الأسئلة الشائعة", url: "faq.html" },
    { title: "الشفافية المالية", url: "transparence.html" },
    { title: "مقياس النتائج", url: "baremetre.html" },
    { title: "الانتساب", url: "adhesion.html" },
    { title: "كونوا شريكًا", url: "partenariat.html" },
    { title: "تقديم تبرع", url: "don.html" },
    { title: "اتصل بنا", url: "contact.html" }
  ]
};

var SEARCH_GROUP_LABELS = {
  fr: { ecole: "Établissements", actualite: "Actualités", document: "Documents", faq: "FAQ", page: "Pages" },
  ar: { ecole: "المدارس", actualite: "الأخبار", document: "الوثائق", faq: "الأسئلة الشائعة", page: "الصفحات" }
};

function initGlobalSearch() {
  var trigger = document.getElementById("nav-search-trigger");
  var overlay = document.getElementById("search-overlay");
  var input = document.getElementById("search-input");
  var closeBtn = document.getElementById("search-close");
  var resultsEl = document.getElementById("search-results");
  if (!trigger || !overlay || !input || !resultsEl || !closeBtn) return;

  var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
  var staticPages = SEARCH_STATIC_PAGES[lang];
  var groupLabels = SEARCH_GROUP_LABELS[lang];
  var placeholder = lang === "ar"
    ? "ابحث عن مدرسة، خبر أو وثيقة..."
    : "Rechercher une école, une actualité, un document...";
  var noResultsText = lang === "ar" ? "لا توجد نتائج." : "Aucun résultat.";
  input.setAttribute("placeholder", placeholder);

  function open() {
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
    setTimeout(function () { input.focus(); }, 50);
  }
  function close() {
    overlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  trigger.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && overlay.classList.contains("open")) close();
  });

  function renderGroups(groups) {
    var order = ["ecole", "actualite", "document", "faq", "page"];
    var html = "";
    order.forEach(function (type) {
      var items = groups[type];
      if (!items || !items.length) return;
      html += '<div class="search-result-group"><h4>' + escapeHtml(groupLabels[type]) + "</h4>";
      items.forEach(function (item) {
        var target = type === "document" ? ' target="_blank" rel="noopener"' : "";
        html +=
          '<a class="search-result-item" href="' + escapeHtml(item.url) + '"' + target + ">" +
          '<span class="search-result-title">' + escapeHtml(item.title) + "</span>" +
          (item.subtitle ? '<span class="search-result-subtitle">' + escapeHtml(item.subtitle) + "</span>" : "") +
          "</a>";
      });
      html += "</div>";
    });
    resultsEl.innerHTML = html || '<p class="search-empty-hint">' + noResultsText + "</p>";
  }

  var debounceTimer = null;
  input.addEventListener("input", function () {
    var term = input.value.trim();
    clearTimeout(debounceTimer);
    if (term.length < 2) {
      resultsEl.innerHTML = "";
      return;
    }
    debounceTimer = setTimeout(function () {
      var termLower = term.toLowerCase();
      var groups = { ecole: [], actualite: [], document: [], faq: [], page: [] };
      staticPages
        .filter(function (p) { return p.title.toLowerCase().indexOf(termLower) !== -1; })
        .forEach(function (p) { groups.page.push(p); });

      fetch(API_BASE + "/api/search?q=" + encodeURIComponent(term))
        .then(function (res) {
          if (!res.ok) throw new Error("API indisponible");
          return res.json();
        })
        .then(function (items) {
          (items || []).forEach(function (item) {
            var url = item.type === "document" ? API_BASE + item.url : item.url;
            if (groups[item.type]) {
              groups[item.type].push({ title: item.title, subtitle: item.subtitle, url: url });
            }
          });
          renderGroups(groups);
        })
        .catch(function () {
          renderGroups(groups);
        });
    }, 300);
  });
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

  var successBox = document.getElementById("adhesion-success");
  var codeEl = document.getElementById("adhesion-code");
  var recepisseLink = document.getElementById("adhesion-recepisse-link");

  var intOrNull = function (selector) {
    var v = valueOf(form, selector);
    return v ? parseInt(v, 10) : null;
  };

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var payload = {
      nom_etablissement: valueOf(form, "#ad-nom-etablissement"),
      nom_directeur: valueOf(form, "#ad-nom-directeur"),
      cycle: valueOf(form, "#ad-cycle") || null,
      type_enseignement: valueOf(form, "#ad-type"),
      telephone: valueOf(form, "#ad-tel"),
      telephone_fixe: valueOf(form, "#ad-tel-fixe") || null,
      email: valueOf(form, "#ad-email") || null,
      localite: valueOf(form, "#ad-localite"),
      boite_postale: valueOf(form, "#ad-boite-postale") || null,
      propriete_terrain: valueOf(form, "#ad-propriete") || null,
      superficie_m2: intOrNull("#ad-superficie"),
      nombre_classes: intOrNull("#ad-classes"),
      nombre_garcons: intOrNull("#ad-garcons"),
      nombre_filles: intOrNull("#ad-filles"),
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
        return res.json();
      })
      .then(function (data) {
        form.style.display = "none";
        if (codeEl) codeEl.textContent = data.code_demande;
        if (recepisseLink) recepisseLink.href = API_BASE + "/api/adhesion-requests/" + data.code_demande + "/recepisse.pdf";
        if (successBox) successBox.style.display = "block";
      })
      .catch(function () {
        btn.textContent = "Erreur — merci de réessayer";
        setTimeout(function () {
          btn.textContent = original;
          btn.disabled = false;
        }, 3500);
      });
  });
}

function initPartenariatForm() {
  var form = document.getElementById("partenariat-form");
  if (!form) return;

  var formCard = document.getElementById("partenariat-form-card");
  var successBox = document.getElementById("partenariat-success");

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var payload = {
      nom: valueOf(form, "#pt-nom"),
      type: valueOf(form, "#pt-type"),
      pays: valueOf(form, "#pt-pays") || null,
      contact_nom: valueOf(form, "#pt-contact-nom"),
      contact_email: valueOf(form, "#pt-contact-email"),
      contact_telephone: valueOf(form, "#pt-contact-tel") || null,
      message: valueOf(form, "#pt-message"),
    };

    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    fetch(API_BASE + "/api/partenariat-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Échec de l'envoi");
        if (formCard) formCard.style.display = "none";
        if (successBox) successBox.style.display = "block";
      })
      .catch(function () {
        btn.textContent = "Erreur — merci de réessayer";
        setTimeout(function () {
          btn.textContent = original;
          btn.disabled = false;
        }, 3500);
      });
  });
}

function initDonForm() {
  var form = document.getElementById("don-form");
  if (!form) return;

  var formCard = document.getElementById("don-form-card");
  var successBox = document.getElementById("don-success");
  var dateInput = document.getElementById("don-date");
  if (dateInput && !dateInput.value) dateInput.value = new Date().toISOString().slice(0, 10);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var payload = {
      nom_donateur: valueOf(form, "#don-nom"),
      email: valueOf(form, "#don-email") || null,
      telephone: valueOf(form, "#don-telephone") || null,
      montant: parseInt(valueOf(form, "#don-montant"), 10),
      date_don: valueOf(form, "#don-date"),
      message: valueOf(form, "#don-message") || null,
    };

    btn.disabled = true;
    btn.textContent = "Envoi en cours…";

    fetch(API_BASE + "/api/dons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Échec de l'envoi");
        if (formCard) formCard.style.display = "none";
        if (successBox) successBox.style.display = "block";
      })
      .catch(function () {
        btn.textContent = "Erreur — merci de réessayer";
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

function loadGalerie() {
  var container = document.getElementById("galerie-grid");
  var emptyEl = document.getElementById("galerie-empty");
  if (!container) return;

  fetch(API_BASE + "/api/photos")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      container.innerHTML = items
        .map(function (p) {
          return (
            '<figure class="galerie-item">' +
            '<img src="' + API_BASE + p.image_url + '" alt="' + escapeHtml(p.caption || "") + '" loading="lazy">' +
            (p.caption ? "<figcaption>" + escapeHtml(p.caption) + "</figcaption>" : "") +
            "</figure>"
          );
        })
        .join("");
    })
    .catch(function () {
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function loadFaq() {
  var container = document.getElementById("faq-list");
  var emptyEl = document.getElementById("faq-empty");
  if (!container) return;

  fetch(API_BASE + "/api/faq")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      container.innerHTML = items
        .map(function (item, index) {
          return (
            '<div class="faq-item" id="faq-' + item.id + '">' +
            '<button class="faq-question" type="button" aria-expanded="false">' +
            "<span>" + escapeHtml(item.question) + "</span>" +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>' +
            "</button>" +
            '<div class="faq-answer"><p>' + escapeHtml(item.reponse).replace(/\n/g, "<br>") + "</p></div>" +
            "</div>"
          );
        })
        .join("");
      container.querySelectorAll(".faq-question").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var item = btn.closest(".faq-item");
          var isOpen = item.classList.contains("open");
          container.querySelectorAll(".faq-item.open").forEach(function (openItem) {
            openItem.classList.remove("open");
            openItem.querySelector(".faq-question").setAttribute("aria-expanded", "false");
          });
          if (!isOpen) {
            item.classList.add("open");
            btn.setAttribute("aria-expanded", "true");
          }
        });
      });
      if (location.hash) {
        var target = document.querySelector(location.hash);
        if (target && target.classList.contains("faq-item")) {
          target.classList.add("open");
          target.querySelector(".faq-question").setAttribute("aria-expanded", "true");
          scrollToHighlight(target);
        }
      }
    })
    .catch(function () {
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function loadTransparence() {
  var container = document.getElementById("transparence-list");
  var emptyEl = document.getElementById("transparence-empty");
  if (!container) return;

  function fcfa(n) {
    return (n || 0).toLocaleString("fr-FR").replace(/ |,/g, " ") + " FCFA";
  }

  fetch(API_BASE + "/api/transparence")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      var ordered = items.slice().reverse();
      container.innerHTML = ordered
        .map(function (a) {
          var solde = a.solde || 0;
          var soldeClass = solde >= 0 ? "positive" : "negative";
          var soldeSign = solde >= 0 ? "+" : "";
          return (
            '<div class="transparence-card">' +
            '<div class="transparence-head">' +
            "<h3>" + escapeHtml(a.annee) + "</h3>" +
            '<span class="transparence-solde ' + soldeClass + '">Solde : ' + soldeSign + fcfa(solde) + "</span>" +
            "</div>" +
            '<div class="transparence-totals">' +
            "<div><strong>" + fcfa(a.total_entrees) + "</strong><span>Total recettes</span></div>" +
            "<div><strong>" + fcfa(a.depenses) + "</strong><span>Total dépenses</span></div>" +
            "</div>" +
            '<div class="transparence-breakdown">' +
            "<div><span>Cotisations</span><strong>" + fcfa(a.cotisations) + "</strong></div>" +
            "<div><span>Adhésions</span><strong>" + fcfa(a.adhesions) + "</strong></div>" +
            "<div><span>Ventes de livres</span><strong>" + fcfa(a.ventes_livres) + "</strong></div>" +
            "<div><span>Droits d'examens</span><strong>" + fcfa(a.droits_examens) + "</strong></div>" +
            "<div><span>Autres recettes</span><strong>" + fcfa(a.recettes) + "</strong></div>" +
            "</div>" +
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
          '<a class="news-read-more" href="actualite.html?id=' + item.id + '">Lire la suite &rarr;</a>' +
          "</div>";
        container.appendChild(el);
      });
    })
    .catch(function () {
      // API indisponible (ex. ouverture locale du fichier) : le contenu statique reste affiché.
    });
}

function loadActualitesFull() {
  var container = document.getElementById("actualites-list");
  var emptyEl = document.getElementById("actualites-empty");
  if (!container) return;

  fetch(API_BASE + "/api/news?limit=100")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      container.innerHTML = items
        .map(function (item) {
          var media = item.image_url
            ? '<img src="' + API_BASE + item.image_url + '" alt="' + escapeHtml(item.title) + '">'
            : '<div class="actualite-card-noimg"><svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5"/></svg></div>';
          return (
            '<a class="actualite-card" href="actualite.html?id=' + item.id + '">' +
            '<div class="actualite-card-media">' + media + "</div>" +
            '<div class="actualite-card-body">' +
            '<span class="news-date">' + formatDateFr(item.published_at) + "</span>" +
            "<h3>" + escapeHtml(item.title) + "</h3>" +
            "<p>" + escapeHtml(item.excerpt) + "</p>" +
            "</div></a>"
          );
        })
        .join("");
    })
    .catch(function () {
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function loadActualiteDetail() {
  var container = document.getElementById("actualite-detail");
  if (!container) return;

  var params = new URLSearchParams(window.location.search);
  var id = params.get("id");
  if (!id) {
    container.innerHTML = '<p style="text-align:center; color:var(--text-muted);">Actualité introuvable.</p>';
    return;
  }

  fetch(API_BASE + "/api/news/" + encodeURIComponent(id))
    .then(function (res) {
      if (!res.ok) throw new Error("Actualité introuvable");
      return res.json();
    })
    .then(function (item) {
      document.title = item.title + " — LECIM";
      var media = item.image_url
        ? '<img src="' + API_BASE + item.image_url + '" alt="' + escapeHtml(item.title) + '" class="actualite-detail-image">'
        : "";
      var body = item.content && item.content.trim() ? item.content : item.excerpt;
      container.innerHTML =
        media +
        '<span class="news-date">' + formatDateFr(item.published_at) + "</span>" +
        "<h1>" + escapeHtml(item.title) + "</h1>" +
        '<div class="actualite-detail-body">' + escapeHtml(body).replace(/\n/g, "<br>") + "</div>";
    })
    .catch(function () {
      container.innerHTML = '<p style="text-align:center; color:var(--text-muted);">Cette actualité est introuvable ou a été retirée.</p>';
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
          (isPast ? "" :
            '<a class="ics-link" href="' + API_BASE + "/api/activities/" + item.id + '/ics" download>' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>' +
            "Ajouter à mon calendrier</a>") +
          "</div>";
        container.appendChild(el);
      });
    })
    .catch(function () {
      // API indisponible : le contenu statique reste affiché.
    });
}

function loadUpcomingEvents() {
  var section = document.getElementById("evenements-section");
  var list = document.getElementById("evenements-list");
  if (!section || !list) return;

  fetch(API_BASE + "/api/activities")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      var upcoming = (items || []).filter(function (i) { return i.status === "upcoming"; }).slice(0, 3);
      if (!upcoming.length) return;
      list.innerHTML = upcoming
        .map(function (item) {
          var d = new Date(item.event_date + "T00:00:00");
          var day = d.toLocaleDateString("fr-FR", { day: "2-digit" });
          var month = d.toLocaleDateString("fr-FR", { month: "short" }).replace(".", "");
          return (
            '<div class="evenement-card">' +
            '<div class="evenement-date-badge"><strong>' + day + "</strong><span>" + escapeHtml(month) + "</span></div>" +
            "<div><h4>" + escapeHtml(item.title) + "</h4>" +
            '<a class="ics-link" href="' + API_BASE + "/api/activities/" + item.id + '/ics" download>' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>' +
            "Ajouter à mon calendrier</a>" +
            "</div></div>"
          );
        })
        .join("");
      section.style.display = "";
    })
    .catch(function () {});
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

function loadFondateurs() {
  var container = document.getElementById("fondateurs-grid");
  if (!container) return;

  fetch(API_BASE + "/api/fondateurs")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      container.innerHTML = "";
      items.forEach(function (item) {
        var card = document.createElement("div");
        card.className = "fondateur-card";
        card.innerHTML =
          '<img class="fondateur-photo" src="' + API_BASE + item.photo_url + '" alt="' + escapeHtml(item.full_name) + '">' +
          "<h4>" + escapeHtml(item.full_name) + "</h4>" +
          (item.role ? '<span class="fondateur-role">' + escapeHtml(item.role) + "</span>" : "") +
          (item.mot ? '<p class="fondateur-mot">' + escapeHtml(item.mot) + "</p>" : "");
        container.appendChild(card);
      });
    })
    .catch(function () {
      // API indisponible : le message par défaut ("aucun fondateur publié") reste affiché.
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

function scrollToHighlight(el) {
  setTimeout(function () {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("search-highlight");
    setTimeout(function () { el.classList.remove("search-highlight"); }, 2200);
  }, 50);
}

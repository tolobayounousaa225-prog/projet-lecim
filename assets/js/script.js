var API_BASE = window.LECIM_API_BASE || "http://localhost:8000";

document.addEventListener("DOMContentLoaded", function () {
  initDataSaverMode();
  initNavToggle();
  initNavDropdowns();
  initLoginLink();
  initHeaderScrollShadow();
  initScrollReveal();
  initHeroParallax();
  initCardTilt();
  initBlurUpImages();
  initReadingProgress();
  initBackToTop();
  initPageTransitions();
  initGalleryLightbox();
  initAdhesionFormProgress();
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
  loadAdhesionWavePayment();
  loadCarte();
  loadResultatsExamens();
  loadEcoles();
  initEcolesMap();
  loadHeroStats();
  loadPartenaires();
  loadInitiatives();
  loadActualitesFull();
  loadActualiteDetail();
  loadGalerie();
  loadFaq();
  loadUpcomingEvents();
  initPushNotifications();
  loadBaremetre();
  loadRessourcesOfficielles();
  loadObjectifsPrincipesMoyens();
  loadConseilAdministration();
  loadTemoignages();
  loadSondageExpress();
  initNewsletterForm();
  initLiveVisitors();
  initWhatsappButton();
  initFaqAssistant();
  recordPageView();
});

function initNewsletterForm() {
  var socialBlock = document.querySelector(".site-footer .footer-social");
  if (!socialBlock || document.getElementById("newsletter-form")) return;

  var wrap = document.createElement("div");
  wrap.style.marginTop = "20px";
  wrap.innerHTML =
    '<h4 style="margin-bottom:8px;">Newsletter</h4>' +
    '<p style="font-size:0.82rem; color:rgba(255,255,255,.65); margin-bottom:10px;">Le résumé mensuel de nos actualités, par e-mail.</p>' +
    '<form id="newsletter-form" style="display:flex; gap:6px; flex-wrap:wrap;">' +
    '<input type="email" id="newsletter-email" required placeholder="Votre e-mail" style="flex:1; min-width:130px; padding:8px 10px; border-radius:6px; border:1px solid rgba(255,255,255,.25); background:rgba(255,255,255,.08); color:#fff; font-size:0.85rem;">' +
    "<button type=\"submit\" class=\"btn btn-primary btn-sm\">S'abonner</button>" +
    "</form>" +
    '<p id="newsletter-msg" style="font-size:0.8rem; margin-top:8px;"></p>';
  socialBlock.parentNode.appendChild(wrap);

  var form = wrap.querySelector("#newsletter-form");
  var emailInput = wrap.querySelector("#newsletter-email");
  var msg = wrap.querySelector("#newsletter-msg");

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var email = emailInput.value.trim();
    if (!email) return;
    var btn = form.querySelector("button");
    btn.disabled = true;
    fetch(API_BASE + "/api/newsletter/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email }),
    })
      .then(function (res) {
        if (res.ok) {
          msg.textContent = "Merci ! Vous êtes inscrit(e) à la newsletter.";
          msg.style.color = "var(--gold-light)";
          form.reset();
        } else {
          msg.textContent = "Adresse e-mail invalide.";
          msg.style.color = "#e08080";
        }
      })
      .catch(function () {
        msg.textContent = "Erreur réseau, réessayez plus tard.";
        msg.style.color = "#e08080";
      })
      .finally(function () {
        btn.disabled = false;
      });
  });
}

function recordPageView() {
  var path = (window.location.pathname + window.location.search).slice(0, 300);
  var payload = JSON.stringify({ path: path });
  try {
    if (navigator.sendBeacon) {
      var blob = new Blob([payload], { type: "application/json" });
      navigator.sendBeacon(API_BASE + "/api/stats/view", blob);
      return;
    }
  } catch (e) {}
  fetch(API_BASE + "/api/stats/view", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
    keepalive: true,
  }).catch(function () {});
}

function initLiveVisitors() {
  var isArabic = document.documentElement.lang === "ar";
  var STORAGE_KEY = "lecim_presence_session_id";
  var HEARTBEAT_MS = 25000;

  var sessionId = "";
  try {
    sessionId = sessionStorage.getItem(STORAGE_KEY) || "";
    if (!sessionId) {
      sessionId = "v-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
      sessionStorage.setItem(STORAGE_KEY, sessionId);
    }
  } catch (e) {
    sessionId = "v-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
  }

  var badge = document.createElement("div");
  badge.id = "live-visitors-badge";
  badge.setAttribute("aria-live", "polite");
  badge.innerHTML =
    '<span class="live-visitors-dot"></span><span id="live-visitors-count">…</span>' +
    '<span class="live-visitors-label">' + (isArabic ? "متصل الآن" : "en ligne") + "</span>";
  document.body.appendChild(badge);

  var countEl = badge.querySelector("#live-visitors-count");

  function applyCount(count) {
    if (typeof count === "number") countEl.textContent = count;
  }

  function sendHeartbeat() {
    fetch(API_BASE + "/api/presence/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) { if (data) applyCount(data.count); })
      .catch(function () {});
  }

  sendHeartbeat();
  setInterval(sendHeartbeat, HEARTBEAT_MS);
}

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

function prefersReducedMotion() {
  return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
}

var DATA_SAVER_STORAGE_KEY = "lecim_data_saver";

function isDataSaverMode() {
  return document.documentElement.classList.contains("data-saver");
}

function initDataSaverMode() {
  var stored = null;
  try { stored = localStorage.getItem(DATA_SAVER_STORAGE_KEY); } catch (e) {}

  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  var autoSlow = !!(conn && (conn.saveData || /2g/.test(conn.effectiveType || "")));
  var active = stored === "on" || (stored !== "off" && autoSlow);

  if (active) document.documentElement.classList.add("data-saver");

  var footerBottom = document.querySelector(".footer-bottom");
  if (!footerBottom) return;
  var isArabic = document.documentElement.lang === "ar";

  var toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "data-saver-toggle";
  toggle.textContent = active
    ? (isArabic ? "إيقاف وضع توفير البيانات" : "Désactiver le mode économie de données")
    : (isArabic ? "تفعيل وضع توفير البيانات" : "Activer le mode économie de données");
  toggle.addEventListener("click", function () {
    try { localStorage.setItem(DATA_SAVER_STORAGE_KEY, active ? "off" : "on"); } catch (e) {}
    window.location.reload();
  });
  footerBottom.appendChild(toggle);
}

function initHeaderScrollShadow() {
  var header = document.querySelector(".site-header");
  if (!header) return;
  function update() {
    if (window.scrollY > 12) header.classList.add("is-scrolled");
    else header.classList.remove("is-scrolled");
  }
  update();
  window.addEventListener("scroll", update, { passive: true });
}

function initScrollReveal() {
  if (prefersReducedMotion() || !("IntersectionObserver" in window)) return;

  var SELECTOR = [
    ".mission-card", ".value-card", ".org-card", ".opm-block",
    ".doc-card", ".news-item", ".faq-item", ".evenement-card",
    ".initiative-card", ".ecole-card", ".ressource-officielle-card",
    ".fondateur-card", ".historique-card", ".actualite-card",
    ".galerie-item", ".section-head"
  ].join(", ");

  var revealObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

  function prepare(el) {
    if (el.classList.contains("reveal")) return;
    el.classList.add("reveal");
    var siblings = el.parentElement ? el.parentElement.children : [];
    var index = Array.prototype.indexOf.call(siblings, el);
    el.style.transitionDelay = (Math.min(index >= 0 ? index % 6 : 0, 5) * 0.06) + "s";
    revealObserver.observe(el);
  }

  document.querySelectorAll(SELECTOR).forEach(prepare);

  var mutationObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches(SELECTOR)) prepare(node);
        if (node.querySelectorAll) node.querySelectorAll(SELECTOR).forEach(prepare);
      });
    });
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });
}

function animateCountUp(el, targetValue, formatFn) {
  if (!el) return;
  if (prefersReducedMotion()) {
    el.textContent = formatFn(targetValue);
    return;
  }
  var duration = 1200;
  var start = null;
  function step(timestamp) {
    if (!start) start = timestamp;
    var progress = Math.min((timestamp - start) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = formatFn(Math.round(targetValue * eased));
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function addSuccessIcon(box) {
  if (!box || box.querySelector(".form-submit-success-icon")) return;
  var icon = document.createElement("div");
  icon.className = "form-submit-success-icon";
  icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>';
  box.insertBefore(icon, box.firstChild);
}

function initHeroParallax() {
  var visual = document.querySelector(".hero-visual");
  if (!visual || prefersReducedMotion() || isDataSaverMode()) return;
  function update() {
    var offset = Math.min(window.scrollY * 0.12, 40);
    visual.style.transform = "translateY(" + offset + "px)";
  }
  update();
  window.addEventListener("scroll", update, { passive: true });
}

function initCardTilt() {
  if (prefersReducedMotion() || isDataSaverMode()) return;
  if (!(window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches)) return;

  var SELECTOR = [
    ".mission-card", ".value-card", ".doc-card", ".opm-block",
    ".evenement-card", ".initiative-card", ".ecole-card",
    ".ressource-officielle-card", ".actualite-card"
  ].join(", ");

  function onMove(e) {
    var card = e.currentTarget;
    var rect = card.getBoundingClientRect();
    var x = (e.clientX - rect.left) / rect.width - 0.5;
    var y = (e.clientY - rect.top) / rect.height - 0.5;
    card.style.transform = "perspective(900px) rotateX(" + (y * -6) + "deg) rotateY(" + (x * 6) + "deg) translateY(-4px)";
  }
  function onLeave(e) {
    e.currentTarget.style.transform = "";
  }
  function prepare(el) {
    if (el.classList.contains("tilt-card")) return;
    el.classList.add("tilt-card");
    el.addEventListener("mousemove", onMove);
    el.addEventListener("mouseleave", onLeave);
  }

  document.querySelectorAll(SELECTOR).forEach(prepare);

  var mutationObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches(SELECTOR)) prepare(node);
        if (node.querySelectorAll) node.querySelectorAll(SELECTOR).forEach(prepare);
      });
    });
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });
}

function initBlurUpImages() {
  if (prefersReducedMotion()) return;

  function prepare(img) {
    if (img.classList.contains("img-blur-up") || img.dataset.noBlur) return;
    img.classList.add("img-blur-up");
    if (img.complete && img.naturalWidth > 0) {
      img.classList.add("is-loaded");
      return;
    }
    img.addEventListener("load", function () { img.classList.add("is-loaded"); }, { once: true });
    img.addEventListener("error", function () { img.classList.add("is-loaded"); }, { once: true });
  }

  document.querySelectorAll('img[loading="lazy"]').forEach(prepare);

  var mutationObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      mutation.addedNodes.forEach(function (node) {
        if (node.nodeType !== 1) return;
        if (node.matches && node.matches('img[loading="lazy"]')) prepare(node);
        if (node.querySelectorAll) node.querySelectorAll('img[loading="lazy"]').forEach(prepare);
      });
    });
  });
  mutationObserver.observe(document.body, { childList: true, subtree: true });
}

function initReadingProgress() {
  var bar = document.createElement("div");
  bar.className = "reading-progress-bar";
  document.body.appendChild(bar);
  function update() {
    var scrollable = document.documentElement.scrollHeight - window.innerHeight;
    var pct = scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0;
    bar.style.width = Math.min(Math.max(pct, 0), 100) + "%";
  }
  update();
  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
}

function initBackToTop() {
  var btn = document.createElement("button");
  btn.type = "button";
  btn.className = "back-to-top";
  btn.setAttribute("aria-label", "Retour en haut de page");
  btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  document.body.appendChild(btn);

  function update() {
    if (window.scrollY > 500) btn.classList.add("is-visible");
    else btn.classList.remove("is-visible");
  }
  update();
  window.addEventListener("scroll", update, { passive: true });
  btn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  });
}

function initPageTransitions() {
  if (prefersReducedMotion()) return;
  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("a[href]") : null;
    if (!link) return;
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (link.target && link.target !== "_self") return;
    if (link.hasAttribute("download")) return;

    var href = link.getAttribute("href");
    if (!href || href.charAt(0) === "#" || href.indexOf("mailto:") === 0 || href.indexOf("tel:") === 0) return;

    var url;
    try { url = new URL(href, window.location.href); } catch (err) { return; }
    if (url.origin !== window.location.origin) return;
    if (url.pathname === window.location.pathname && url.hash) return;

    e.preventDefault();
    document.body.classList.add("page-fade-out");
    setTimeout(function () { window.location.href = url.href; }, 200);
  });
}

function showSkeleton(container, count) {
  if (!container) return;
  var html = "";
  for (var i = 0; i < count; i++) html += '<div class="skeleton-card"></div>';
  container.innerHTML = html;
}

function initGalleryLightbox() {
  var grid = document.getElementById("galerie-grid");
  if (!grid) return;

  var overlay = document.createElement("div");
  overlay.className = "lightbox-overlay";
  overlay.innerHTML =
    '<button type="button" class="lightbox-close" aria-label="Fermer">' +
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button>' +
    '<img alt="">' +
    '<div class="lightbox-caption"></div>';
  document.body.appendChild(overlay);
  var img = overlay.querySelector("img");
  var caption = overlay.querySelector(".lightbox-caption");

  function open(src, alt) {
    img.src = src;
    img.alt = alt || "";
    caption.textContent = alt || "";
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function close() {
    overlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  grid.addEventListener("click", function (e) {
    var figure = e.target.closest ? e.target.closest(".galerie-item") : null;
    if (!figure) return;
    var image = figure.querySelector("img");
    if (!image) return;
    open(image.src, image.alt);
  });
  overlay.querySelector(".lightbox-close").addEventListener("click", close);
  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && overlay.classList.contains("open")) close();
  });
}

function initAdhesionFormProgress() {
  var form = document.getElementById("adhesion-form");
  if (!form) return;

  var wrap = document.createElement("div");
  wrap.className = "form-progress-wrap";
  wrap.innerHTML =
    '<div class="form-progress-label"><span>Progression du formulaire</span><span class="form-progress-percent">0%</span></div>' +
    '<div class="form-progress-track"><div class="form-progress-fill"></div></div>';
  form.parentElement.insertBefore(wrap, form);
  var fill = wrap.querySelector(".form-progress-fill");
  var percentEl = wrap.querySelector(".form-progress-percent");

  var fields = Array.prototype.slice.call(
    form.querySelectorAll("input, select, textarea")
  ).filter(function (f) { return f.type !== "hidden"; });

  function update() {
    if (!fields.length) return;
    var filled = fields.filter(function (f) {
      if (f.type === "checkbox" || f.type === "radio") return f.checked;
      return f.value && String(f.value).trim().length > 0;
    }).length;
    var pct = Math.round((filled / fields.length) * 100);
    fill.style.width = pct + "%";
    percentEl.textContent = pct + "%";
  }

  fields.forEach(function (f) {
    f.addEventListener("input", update);
    f.addEventListener("change", update);
  });
  update();
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
      var plusFormat = function (v) { return v + "+"; };
      var elevesFormat = function (v) { return v.toLocaleString("fr-FR") + "+"; };
      if (ecolesEl && stats.ecoles) animateCountUp(ecolesEl, stats.ecoles, plusFormat);
      if (regionsEl && stats.regions) animateCountUp(regionsEl, stats.regions, plusFormat);
      if (enseignantsEl && stats.enseignants) animateCountUp(enseignantsEl, stats.enseignants, plusFormat);
      if (elevesEl && stats.eleves) animateCountUp(elevesEl, stats.eleves, elevesFormat);
      if (badgeEcolesEl && stats.ecoles) animateCountUp(badgeEcolesEl, stats.ecoles, plusFormat);
      if (badgeRegionsEl && stats.regions) animateCountUp(badgeRegionsEl, stats.regions, plusFormat);
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
  var bgElements = document.querySelectorAll("[data-content-bg-key]");
  if (!elements.length && !bgElements.length) return;

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
      bgElements.forEach(function (el) {
        var url = values[el.getAttribute("data-content-bg-key")];
        if (!url || isDataSaverMode()) return;
        el.style.backgroundImage =
          "linear-gradient(135deg, rgba(10,61,99,.88) 0%, rgba(4,56,114,.82) 55%, rgba(8,58,92,.90) 100%), url('" +
          API_BASE + url + "')";
        el.style.backgroundSize = "cover";
        el.style.backgroundPosition = "center";
        el.classList.add("has-bg-image");
      });
    })
    .catch(function () {
      // API indisponible : les textes/visuels par défaut codés dans la page restent affichés.
    });
}

function initTextToSpeech(btn, text) {
  if (!btn) return;
  if (!("speechSynthesis" in window) || !text) {
    btn.style.display = "none";
    return;
  }
  var isArabic = document.documentElement.lang === "ar";
  var labelPlay = isArabic ? "🔊 استماع للمقال" : "🔊 Écouter l'article";
  var labelStop = isArabic ? "⏹ إيقاف" : "⏹ Arrêter la lecture";
  btn.textContent = labelPlay;

  btn.addEventListener("click", function () {
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      btn.textContent = labelPlay;
      return;
    }
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = isArabic ? "ar" : "fr-FR";
    utterance.onend = function () { btn.textContent = labelPlay; };
    utterance.onerror = function () { btn.textContent = labelPlay; };
    window.speechSynthesis.speak(utterance);
    btn.textContent = labelStop;
  });

  window.addEventListener("beforeunload", function () {
    if (window.speechSynthesis.speaking) window.speechSynthesis.cancel();
  });
}

function initEcolesMap() {
  var mapContainer = document.getElementById("ecoles-map");
  var emptyEl = document.getElementById("ecoles-map-empty");
  var listWrap = document.getElementById("ecoles-list-wrap");
  var viewButtons = document.querySelectorAll(".ecoles-view-btn");
  if (!mapContainer || !viewButtons.length) return;

  var map = null;
  var loaded = false;

  function ensureMap() {
    if (typeof L === "undefined") return;
    if (!map) {
      map = L.map(mapContainer).setView([7.54, -5.55], 7);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; contributeurs OpenStreetMap",
        maxZoom: 18,
      }).addTo(map);
    }
    if (loaded) {
      setTimeout(function () { map.invalidateSize(); }, 0);
      return;
    }
    loaded = true;

    fetch(API_BASE + "/api/carte")
      .then(function (res) {
        if (!res.ok) throw new Error("indisponible");
        return res.json();
      })
      .then(function (markers) {
        var ecoles = (markers || []).filter(function (m) { return m.type === "etablissement"; });
        if (!ecoles.length) {
          if (emptyEl) emptyEl.style.display = "block";
          return;
        }
        var bounds = [];
        ecoles.forEach(function (m) {
          var icon = L.divIcon({
            className: "",
            html: '<div style="width:16px;height:16px;border-radius:50%;background:#043872;border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4);"></div>',
            iconSize: [16, 16],
            iconAnchor: [8, 8],
          });
          var popup = "<strong>" + escapeHtml(m.nom) + "</strong>" + (m.detail ? "<br>" + escapeHtml(m.detail) : "");
          L.marker([m.latitude, m.longitude], { icon: icon }).addTo(map).bindPopup(popup);
          bounds.push([m.latitude, m.longitude]);
        });
        if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 10 });
        setTimeout(function () { map.invalidateSize(); }, 0);
      })
      .catch(function () {
        if (emptyEl) emptyEl.style.display = "block";
      });
  }

  viewButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var view = btn.getAttribute("data-view");
      viewButtons.forEach(function (b) { b.classList.toggle("active", b === btn); });
      if (view === "carte") {
        if (listWrap) listWrap.style.display = "none";
        mapContainer.style.display = "block";
        ensureMap();
      } else {
        mapContainer.style.display = "none";
        if (listWrap) listWrap.style.display = "";
      }
    });
  });
}

function initFaqAssistant() {
  var isArabic = document.documentElement.lang === "ar";
  var L = {
    label: isArabic ? "المساعد الافتراضي" : "Assistant LECIM",
    placeholder: isArabic ? "اكتبوا سؤالكم..." : "Posez votre question...",
    greeting: isArabic
      ? "مرحبًا! اطرحوا سؤالكم حول الانتساب أو الامتحانات أو الاتصال بنا."
      : "Bonjour ! Posez-moi une question sur l'adhésion, les examens, le contact...",
    notFound: isArabic
      ? "لم أجد إجابة دقيقة لهذا السؤال. يمكنكم التواصل معنا مباشرة."
      : "Je n'ai pas trouvé de réponse précise à cette question. Vous pouvez nous contacter directement.",
    contactLink: isArabic ? "اتصل بنا" : "Nous contacter",
    thinking: "…",
  };

  var toggle = document.createElement("button");
  toggle.type = "button";
  toggle.id = "faq-assistant-toggle";
  toggle.setAttribute("aria-label", L.label);
  toggle.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  var panel = document.createElement("div");
  panel.id = "faq-assistant-panel";
  panel.innerHTML =
    '<div class="faq-assistant-header"><strong>' + L.label + "</strong>" +
    '<button type="button" id="faq-assistant-close" aria-label="Fermer">&times;</button></div>' +
    '<div id="faq-assistant-messages"></div>' +
    '<form id="faq-assistant-form">' +
    '<input type="text" id="faq-assistant-input" placeholder="' + L.placeholder + '" autocomplete="off" maxlength="300">' +
    '<button type="submit" aria-label="Envoyer"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 21l21-9L2 3v7l15 2-15 2z"/></svg></button>' +
    "</form>";

  document.body.appendChild(toggle);
  document.body.appendChild(panel);

  var messages = panel.querySelector("#faq-assistant-messages");
  var form = panel.querySelector("#faq-assistant-form");
  var input = panel.querySelector("#faq-assistant-input");
  var opened = false;

  function addMessage(text, who, isHtml) {
    var el = document.createElement("div");
    el.className = "faq-msg faq-msg-" + who;
    if (isHtml) el.innerHTML = text; else el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function openPanel() {
    if (opened) return;
    opened = true;
    panel.classList.add("is-open");
    if (!messages.children.length) addMessage(L.greeting, "bot");
    input.focus();
  }
  function closePanel() {
    opened = false;
    panel.classList.remove("is-open");
  }

  toggle.addEventListener("click", function () {
    if (opened) closePanel(); else openPanel();
  });
  panel.querySelector("#faq-assistant-close").addEventListener("click", closePanel);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (!q) return;
    addMessage(q, "user");
    input.value = "";
    var thinkingEl = addMessage(L.thinking, "bot");

    fetch(API_BASE + "/api/assistant/ask?q=" + encodeURIComponent(q))
      .then(function (res) {
        if (!res.ok) throw new Error("indisponible");
        return res.json();
      })
      .then(function (data) {
        thinkingEl.remove();
        if (data.found) {
          addMessage(escapeHtml(data.reponse), "bot", true);
        } else {
          addMessage(escapeHtml(L.notFound) + ' <a href="contact.html">' + escapeHtml(L.contactLink) + "</a>", "bot", true);
        }
      })
      .catch(function () {
        thinkingEl.remove();
        addMessage(escapeHtml(L.notFound) + ' <a href="contact.html">' + escapeHtml(L.contactLink) + "</a>", "bot", true);
      });
  });
}

function initActualiteShareButton(btn, newsId, title) {
  if (!btn) return;
  var isArabic = document.documentElement.lang === "ar";
  var shareUrl = API_BASE + "/actualite/" + encodeURIComponent(newsId);
  var label = isArabic ? "🔗 مشاركة" : "🔗 Partager";
  var copiedLabel = isArabic ? "✓ تم نسخ الرابط" : "✓ Lien copié";
  btn.textContent = label;

  btn.addEventListener("click", function () {
    if (navigator.share) {
      navigator.share({ title: title, url: shareUrl }).catch(function () {});
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(shareUrl).then(function () {
        btn.textContent = copiedLabel;
        setTimeout(function () { btn.textContent = label; }, 2000);
      });
    }
  });
}

function initWhatsappButton() {
  var btn = document.createElement("a");
  btn.id = "whatsapp-float-btn";
  btn.target = "_blank";
  btn.rel = "noopener";
  btn.setAttribute("aria-label", "Discuter sur WhatsApp");
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.1-1.7-.8-1.9-.9-.3-.1-.4-.1-.6.1-.2.3-.7.9-.8 1-.1.2-.3.2-.6.1-.3-.1-1.2-.5-2.3-1.5-.9-.8-1.4-1.7-1.6-2-.2-.3 0-.5.1-.6.1-.1.3-.3.4-.5.1-.1.2-.3.2-.4.1-.2 0-.3 0-.5s-.6-1.5-.8-2c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.3.3-1 .9-1 2.3s1 2.7 1.1 2.9c.1.2 2 3 4.8 4.3.7.3 1.2.5 1.6.6.7.2 1.3.2 1.8.1.5-.1 1.7-.7 1.9-1.3.2-.6.2-1.2.2-1.3-.1-.1-.3-.2-.6-.3z"/><path d="M12 2C6.5 2 2 6.5 2 12c0 1.8.5 3.6 1.4 5.1L2 22l5-1.3c1.4.8 3.1 1.2 4.9 1.2h.1c5.5 0 10-4.5 10-10S17.5 2 12 2zm0 18.3h-.1c-1.6 0-3.2-.4-4.6-1.2l-.3-.2-3.5.9.9-3.4-.2-.3C3.4 14.6 3 13.3 3 12 3 7.1 7.1 3 12 3s9 4.1 9 9-4.1 8.3-9 8.3z"/></svg>';
  document.body.appendChild(btn);

  fetch(API_BASE + "/api/site-content")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (values) {
      var numero = values.whatsapp_numero;
      if (!numero) return;
      var message = values.whatsapp_message || "";
      btn.href = "https://wa.me/" + encodeURIComponent(numero) + (message ? "?text=" + encodeURIComponent(message) : "");
      btn.style.display = "flex";
    })
    .catch(function () {
      // API indisponible ou WhatsApp non configuré par l'admin : le bouton reste masqué.
    });
}

function loadAdhesionWavePayment() {
  var container = document.getElementById("adhesion-wave-payment");
  if (!container) return;

  var linkEl = document.getElementById("adhesion-wave-link");
  var qrImg = document.getElementById("adhesion-wave-qr-img");

  fetch(API_BASE + "/api/site-content")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (values) {
      var link = values.adhesion_wave_link;
      if (!link) return;
      if (linkEl) linkEl.href = link;
      if (qrImg && values.adhesion_wave_qr) {
        qrImg.src = API_BASE + values.adhesion_wave_qr;
        qrImg.style.display = "";
      }
      container.style.display = "block";
    })
    .catch(function () {
      // API indisponible ou paiement Wave non configuré par l'admin : le bloc reste masqué.
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
  showSkeleton(list, 6);

  var regionsNav = document.getElementById("ecoles-regions-nav");
  var countEl = document.getElementById("ecoles-count-num");
  var countLabelEl = document.getElementById("ecoles-count-label");
  var emptyEl = document.getElementById("ecoles-empty");
  var searchInput = document.getElementById("ecoles-search-input");
  var regionSelect = document.getElementById("ecoles-region-select");
  var tabs = document.querySelectorAll(".ecoles-tab");

  var niveauLabels = { primaire: "Primaire", secondaire: "Secondaire", les_deux: "Primaire & secondaire" };
  var countLabelDefault = countLabelEl ? countLabelEl.textContent : "";
  var countLabels = { membre: countLabelDefault, partenaire: "partenaire(s)" };
  var allEcoles = [];
  var currentCategorie = "membre";
  var CARET = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>';

  var slug = function (prefix, s) {
    return prefix + "-" + s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-");
  };

  function applySearch() {
    var term = searchInput.value.trim().toLowerCase();
    var visibleTotal = 0;
    document.querySelectorAll(".ecole-zone").forEach(function (zoneEl) {
      var zoneMatches = zoneEl.getAttribute("data-zone").indexOf(term) !== -1;
      var visibleInZone = 0;
      zoneEl.querySelectorAll(".ecole-commune").forEach(function (communeEl) {
        var communeMatches = zoneMatches || communeEl.getAttribute("data-commune").indexOf(term) !== -1;
        var visibleInCommune = 0;
        communeEl.querySelectorAll(".ecole-card").forEach(function (card) {
          var match = communeMatches || card.getAttribute("data-nom").indexOf(term) !== -1;
          card.style.display = match ? "" : "none";
          if (match) visibleInCommune++;
        });
        communeEl.style.display = visibleInCommune ? "" : "none";
        communeEl.classList.toggle("open", term ? visibleInCommune > 0 : false);
        visibleInZone += visibleInCommune;
      });
      zoneEl.style.display = visibleInZone ? "" : "none";
      zoneEl.classList.toggle("open", term ? visibleInZone > 0 : false);
      visibleTotal += visibleInZone;
    });
    countEl.textContent = visibleTotal;
    emptyEl.style.display = visibleTotal ? "none" : "block";
  }

  function render() {
    var ecoles = allEcoles.filter(function (e) { return (e.categorie || "membre") === currentCategorie; });
    if (countLabelEl) countLabelEl.textContent = countLabels[currentCategorie] || countLabelDefault;

    if (!ecoles.length) {
      regionsNav.innerHTML = "";
      list.innerHTML = "";
      countEl.textContent = "0";
      emptyEl.style.display = "block";
      return;
    }
    emptyEl.style.display = "none";

    var zones = {};
    ecoles.forEach(function (e) {
      var zoneName = (e.region || e.district || "").trim() || "Autre";
      var commune = (e.bureau_local || "").trim() || "Non précisée";
      if (!zones[zoneName]) zones[zoneName] = {};
      if (!zones[zoneName][commune]) zones[zoneName][commune] = [];
      zones[zoneName][commune].push(e);
    });
    var zoneNames = Object.keys(zones).sort(function (a, b) {
      if (a === "Autre") return 1;
      if (b === "Autre") return -1;
      return a.localeCompare(b, "fr");
    });

    var navHtml = "";
    zoneNames.forEach(function (zoneName) {
      var total = Object.keys(zones[zoneName]).reduce(function (sum, c) { return sum + zones[zoneName][c].length; }, 0);
      navHtml += '<a href="#' + slug("zone", zoneName) + '">' + escapeHtml(zoneName) + " (" + total + ")</a>";
    });
    regionsNav.innerHTML = navHtml;

    if (regionSelect) {
      var previousValue = regionSelect.value;
      var optionsHtml = '<option value="">' + regionSelect.options[0].textContent + "</option>";
      zoneNames.forEach(function (zoneName) {
        optionsHtml += '<option value="' + escapeHtml(zoneName) + '">' + escapeHtml(zoneName) + "</option>";
      });
      regionSelect.innerHTML = optionsHtml;
      regionSelect.value = zoneNames.indexOf(previousValue) !== -1 ? previousValue : "";
    }

    var listHtml = "";
    zoneNames.forEach(function (zoneName) {
      var communes = zones[zoneName];
      var communeNames = Object.keys(communes).sort(function (a, b) {
        if (a === "Non précisée") return 1;
        if (b === "Non précisée") return -1;
        return a.localeCompare(b, "fr");
      });
      var zoneTotal = communeNames.reduce(function (sum, c) { return sum + communes[c].length; }, 0);

      listHtml += '<div class="ecole-zone" id="' + slug("zone", zoneName) + '" data-zone="' + escapeHtml(zoneName.toLowerCase()) + '">';
      listHtml += '<button type="button" class="ecole-zone-header" aria-expanded="false">';
      listHtml += '<span class="ecole-zone-name">' + escapeHtml(zoneName) + "</span>";
      listHtml += '<span class="ecole-zone-count">' + zoneTotal + "</span>" + CARET + "</button>";
      listHtml += '<div class="ecole-zone-body"><div class="ecole-zone-body-inner">';

      communeNames.forEach(function (communeName) {
        var items = communes[communeName];
        listHtml += '<div class="ecole-commune" id="' + slug("commune", zoneName + "-" + communeName) + '" data-commune="' + escapeHtml(communeName.toLowerCase()) + '">';
        listHtml += '<button type="button" class="ecole-commune-header" aria-expanded="false">';
        listHtml += '<span class="ecole-commune-name">' + escapeHtml(communeName) + "</span>";
        listHtml += '<span class="ecole-commune-count">' + items.length + "</span>" + CARET + "</button>";
        listHtml += '<div class="ecole-commune-body"><div class="ecole-commune-body-inner"><div class="ecole-grid">';

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

        listHtml += "</div></div></div></div>";
      });

      listHtml += "</div></div></div>";
    });
    list.innerHTML = listHtml;
    countEl.textContent = ecoles.length;

    if (location.hash) {
      var target = document.querySelector(location.hash);
      if (target && target.classList.contains("ecole-card")) {
        var communeAncestor = target.closest(".ecole-commune");
        var zoneAncestor = target.closest(".ecole-zone");
        if (communeAncestor) communeAncestor.classList.add("open");
        if (zoneAncestor) zoneAncestor.classList.add("open");
        scrollToHighlight(target);
      } else if (target && (target.classList.contains("ecole-zone") || target.id.indexOf("zone-") === 0)) {
        target.classList.add("open");
      }
    }

    if (searchInput && searchInput.value.trim()) applySearch();
  }

  list.addEventListener("click", function (e) {
    var zoneHeader = e.target.closest(".ecole-zone-header");
    if (zoneHeader) {
      var zone = zoneHeader.closest(".ecole-zone");
      var willOpen = !zone.classList.contains("open");
      zone.classList.toggle("open", willOpen);
      zoneHeader.setAttribute("aria-expanded", String(willOpen));
      return;
    }
    var communeHeader = e.target.closest(".ecole-commune-header");
    if (communeHeader) {
      var commune = communeHeader.closest(".ecole-commune");
      var willOpenC = !commune.classList.contains("open");
      commune.classList.toggle("open", willOpenC);
      communeHeader.setAttribute("aria-expanded", String(willOpenC));
    }
  });

  regionsNav.addEventListener("click", function (e) {
    var link = e.target.closest("a");
    if (!link) return;
    var target = document.querySelector(link.getAttribute("href"));
    if (target) target.classList.add("open");
  });

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      if (tab.classList.contains("active")) return;
      tabs.forEach(function (t) {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      currentCategorie = tab.getAttribute("data-categorie");
      if (searchInput) searchInput.value = "";
      if (regionSelect) regionSelect.value = "";
      render();
    });
  });

  fetch(API_BASE + "/api/etablissements")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (ecoles) {
      allEcoles = ecoles || [];
      if (!allEcoles.length) {
        emptyEl.style.display = "block";
        return;
      }
      render();
      if (searchInput) {
        searchInput.addEventListener("input", function () {
          if (regionSelect) regionSelect.value = "";
          applySearch();
        });
      }
      if (regionSelect) {
        regionSelect.addEventListener("change", function () {
          if (searchInput) searchInput.value = regionSelect.value;
          applySearch();
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
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + (r.nombre_admis_garcons || 0) + "</td>" +
              '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right;">' + (r.nombre_admis_filles || 0) + "</td>" +
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

function tauxCellHtml(taux) {
  var cls = tauxPillClass(taux);
  return (
    '<td style="padding:10px; border-bottom:1px solid var(--border); text-align:right; min-width:150px;">' +
    '<span class="taux-pill ' + cls + '">' + taux + "%</span>" +
    '<div class="taux-bar-track"><div class="taux-bar-fill ' + cls + '" data-target="' + taux + '"></div></div>' +
    "</td>"
  );
}

function animateTauxBars(root) {
  if (!root) return;
  var bars = root.querySelectorAll(".taux-bar-fill[data-target]");
  if (!bars.length) return;
  if (prefersReducedMotion() || !("IntersectionObserver" in window)) {
    bars.forEach(function (b) { b.style.width = b.dataset.target + "%"; });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.style.width = entry.target.dataset.target + "%";
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });
  bars.forEach(function (b) { observer.observe(b); });
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
              tauxCellHtml(r.taux_reussite) +
              "</tr>"
            );
          })
          .join("");
        animateTauxBars(nationalBody);
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
              tauxCellHtml(r.taux_reussite) +
              "</tr>"
            );
          })
          .join("");
        animateTauxBars(regionalBody);
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

function initNavDropdowns() {
  document.querySelectorAll(".dropdown-toggle").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      var li = btn.closest("li");
      var willOpen = !li.classList.contains("dropdown-open");
      document.querySelectorAll(".nav-pill li.dropdown-open").forEach(function (openLi) {
        openLi.classList.remove("dropdown-open");
        var openBtn = openLi.querySelector(".dropdown-toggle");
        if (openBtn) openBtn.setAttribute("aria-expanded", "false");
      });
      if (willOpen) {
        li.classList.add("dropdown-open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });
}

function initContactForm() {
  var form = document.getElementById("contact-form");
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

  var params = new URLSearchParams(location.search);
  var projetId = params.get("projet_id");
  var projetTitre = params.get("titre");
  if (projetId && projetTitre) {
    var noteEl = document.getElementById("partenariat-projet-note");
    var titreEl = document.getElementById("partenariat-projet-titre");
    var hiddenInput = document.getElementById("pt-projet-id");
    if (titreEl) titreEl.textContent = projetTitre;
    if (hiddenInput) hiddenInput.value = projetId;
    if (noteEl) noteEl.style.display = "block";
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    var original = btn.textContent;

    var projetIdValue = valueOf(form, "#pt-projet-id");
    var payload = {
      nom: valueOf(form, "#pt-nom"),
      type: valueOf(form, "#pt-type"),
      pays: valueOf(form, "#pt-pays") || null,
      contact_nom: valueOf(form, "#pt-contact-nom"),
      contact_email: valueOf(form, "#pt-contact-email"),
      contact_telephone: valueOf(form, "#pt-contact-tel") || null,
      message: valueOf(form, "#pt-message"),
      projet_id: projetIdValue ? parseInt(projetIdValue, 10) : null,
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
        if (successBox) { addSuccessIcon(successBox); successBox.style.display = "block"; }
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
        if (successBox) { addSuccessIcon(successBox); successBox.style.display = "block"; }
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
  showSkeleton(container, 3);

  fetch(API_BASE + "/api/projets")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        container.innerHTML = "";
        if (emptyEl) emptyEl.style.display = "block";
        return;
      }
      if (emptyEl) emptyEl.style.display = "none";
      var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
      var linkLabel = lang === "ar" ? "كونوا شركاء في هذا المشروع ←" : "Devenir partenaire de ce projet →";
      container.innerHTML = items
        .map(function (p) {
          var partenaireUrl = "partenariat.html?projet_id=" + encodeURIComponent(p.id) + "&titre=" + encodeURIComponent(p.titre);
          return (
            '<div class="initiative-card"><span class="initiative-statut">' +
            escapeHtml(p.statut_label) +
            "</span><h3>" +
            escapeHtml(p.titre) +
            "</h3>" +
            (p.description ? "<p>" + escapeHtml(p.description) + "</p>" : "") +
            '<a href="' + partenaireUrl + '" class="initiative-partenaire-link">' + linkLabel + "</a>" +
            "</div>"
          );
        })
        .join("");
    })
    .catch(function () {
      container.innerHTML = "";
      if (emptyEl) emptyEl.style.display = "block";
    });
}

function loadGalerie() {
  var container = document.getElementById("galerie-grid");
  var emptyEl = document.getElementById("galerie-empty");
  if (!container) return;
  showSkeleton(container, 6);

  fetch(API_BASE + "/api/photos")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        container.innerHTML = "";
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
      container.innerHTML = "";
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

function valueOf(form, selector) {
  var el = form.querySelector(selector);
  return el ? el.value.trim() : "";
}

function loadNews() {
  var container = document.querySelector(".news-list");
  if (!container) return;
  showSkeleton(container, 3);

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
  showSkeleton(container, 6);

  fetch(API_BASE + "/api/news?limit=100")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) {
        container.innerHTML = "";
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
      container.innerHTML = "";
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
        '<div class="actualite-detail-actions">' +
        '<button type="button" id="actualite-listen-btn" class="tts-btn"></button>' +
        '<button type="button" id="actualite-share-btn" class="tts-btn"></button>' +
        "</div>" +
        '<div class="actualite-detail-body">' + escapeHtml(body).replace(/\n/g, "<br>") + "</div>";
      initTextToSpeech(document.getElementById("actualite-listen-btn"), item.title + ". " + body);
      initActualiteShareButton(document.getElementById("actualite-share-btn"), id, item.title);
    })
    .catch(function () {
      container.innerHTML = '<p style="text-align:center; color:var(--text-muted);">Cette actualité est introuvable ou a été retirée.</p>';
    });
}

function loadActivities() {
  var container = document.querySelector(".timeline");
  if (!container) return;
  showSkeleton(container, 4);

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
  showSkeleton(list, 3);

  fetch(API_BASE + "/api/activities")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      var upcoming = (items || []).filter(function (i) { return i.status === "upcoming"; }).slice(0, 3);
      if (!upcoming.length) { list.innerHTML = ""; return; }
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
    .catch(function () { list.innerHTML = ""; });
}

var RESSOURCE_OFFICIELLE_SECTIONS_JS = ["manuel_scolaire", "programme_officiel", "enseignement_islamique"];
var RESSOURCE_LANGUE_LABELS = {
  fr: { arabe: "Arabe", francais: "Français" },
  ar: { arabe: "العربية", francais: "الفرنسية" },
};

function loadRessourcesOfficielles() {
  var hasContainer = RESSOURCE_OFFICIELLE_SECTIONS_JS.some(function (sec) {
    return document.getElementById("ressources-" + sec + "-grid");
  });
  if (!hasContainer) return;

  var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
  var downloadLabel = lang === "ar" ? "تحميل" : "Télécharger";
  var langueLabels = RESSOURCE_LANGUE_LABELS[lang];

  fetch(API_BASE + "/api/ressources-officielles")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      var bySection = {};
      (items || []).forEach(function (item) {
        var sec = item.section || "autre";
        if (!bySection[sec]) bySection[sec] = [];
        bySection[sec].push(item);
      });

      RESSOURCE_OFFICIELLE_SECTIONS_JS.forEach(function (sec) {
        var grid = document.getElementById("ressources-" + sec + "-grid");
        var emptyEl = document.getElementById("ressources-" + sec + "-empty");
        if (!grid) return;
        var docs = bySection[sec] || [];
        if (!docs.length) {
          grid.innerHTML = "";
          if (emptyEl) emptyEl.style.display = "block";
          return;
        }
        if (emptyEl) emptyEl.style.display = "none";
        grid.innerHTML = docs
          .map(function (item) {
            var langueLabel = langueLabels[item.langue] || "";
            return (
              '<div class="ressource-officielle-card">' +
              '<div class="ressource-officielle-photo">' +
              '<img src="' + API_BASE + item.photo_url + '" alt="' + escapeHtml(item.titre) + '" loading="lazy">' +
              (langueLabel ? '<span class="ressource-officielle-langue">' + escapeHtml(langueLabel) + "</span>" : "") +
              "</div>" +
              '<div class="ressource-officielle-body">' +
              "<h4>" + escapeHtml(item.titre) + "</h4>" +
              (item.description ? "<p>" + escapeHtml(item.description) + "</p>" : "") +
              (item.file_url ? '<a href="' + API_BASE + item.file_url + '" class="ressource-officielle-download" target="_blank" rel="noopener">' + downloadLabel + "</a>" : "") +
              "</div>" +
              "</div>"
            );
          })
          .join("");
      });
    })
    .catch(function () {});
}

var OPM_CATEGORIES_JS = ["objectif", "principe", "moyen"];

function loadObjectifsPrincipesMoyens() {
  var hasContainer = OPM_CATEGORIES_JS.some(function (cat) {
    return document.getElementById("opm-" + cat + "-list");
  });
  if (!hasContainer) return;

  fetch(API_BASE + "/api/objectifs-principes-moyens")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      var byCategorie = {};
      (items || []).forEach(function (item) {
        var cat = item.categorie || "autre";
        if (!byCategorie[cat]) byCategorie[cat] = [];
        byCategorie[cat].push(item);
      });

      OPM_CATEGORIES_JS.forEach(function (cat) {
        var list = document.getElementById("opm-" + cat + "-list");
        var emptyEl = document.getElementById("opm-" + cat + "-empty");
        if (!list) return;
        var entries = byCategorie[cat] || [];
        if (!entries.length) {
          list.innerHTML = "";
          if (emptyEl) emptyEl.style.display = "block";
          return;
        }
        if (emptyEl) emptyEl.style.display = "none";
        list.innerHTML = entries
          .map(function (item) { return "<li>" + escapeHtml(item.contenu) + "</li>"; })
          .join("");
      });
    })
    .catch(function () {});
}

var PUBLICATION_CATEGORY_LABELS = {
  reglement_interieur: "Règlement Intérieur",
  statuts: "Statuts de la LECIM",
  resultats_examens: "Résultats aux examens nationaux",
  kit_presse: "Kit presse & médias",
  rapport_impact: "Rapports d'impact annuels",
  autre: "Autres documents",
};
var PUBLICATION_CATEGORY_ORDER = ["reglement_interieur", "statuts", "resultats_examens", "kit_presse", "rapport_impact", "autre"];

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

function renderSondageExpressResults(container, sondage) {
  var total = sondage.total_votes || 0;
  var rows = sondage.options
    .map(function (o) {
      var pct = total > 0 ? Math.round((o.votes / total) * 100) : 0;
      return (
        '<div class="sondage-express-result-row">' +
        '<div class="sondage-express-result-label"><span>' + escapeHtml(o.texte) + "</span><span>" + pct + "%</span></div>" +
        '<div class="sondage-express-result-track"><div class="sondage-express-result-fill" style="width:' + pct + '%"></div></div>' +
        "</div>"
      );
    })
    .join("");
  var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
  var totalLabel = lang === "ar"
    ? total + " صوت — شكرا لمشاركتكم"
    : total + " vote" + (total > 1 ? "s" : "") + " — merci pour votre participation";
  container.innerHTML =
    '<div class="sondage-express-card">' +
    '<div class="sondage-express-question">' + escapeHtml(sondage.question) + "</div>" +
    '<div class="sondage-express-results">' + rows + "</div>" +
    '<div class="sondage-express-total">' + totalLabel + "</div>" +
    "</div>";
}

function loadSondageExpress() {
  var container = document.getElementById("sondage-express-widget");
  var section = document.getElementById("sondage-express-section");
  if (!container) return;

  fetch(API_BASE + "/api/sondages-express/actif")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (sondage) {
      if (!sondage) return;
      if (section) section.style.display = "";

      var votedKey = "lecim_sondage_express_voted_" + sondage.id;
      if (localStorage.getItem(votedKey)) {
        renderSondageExpressResults(container, sondage);
        return;
      }

      var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
      var optionsHtml = sondage.options
        .map(function (o) {
          return '<button type="button" class="sondage-express-option" data-option-id="' + o.id + '">' + escapeHtml(o.texte) + "</button>";
        })
        .join("");
      container.innerHTML =
        '<div class="sondage-express-card">' +
        '<div class="sondage-express-question">' + escapeHtml(sondage.question) + "</div>" +
        '<div class="sondage-express-options">' + optionsHtml + "</div>" +
        "</div>";

      container.querySelectorAll(".sondage-express-option").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var optionId = parseInt(btn.getAttribute("data-option-id"), 10);
          fetch(API_BASE + "/api/sondages-express/" + sondage.id + "/vote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ option_id: optionId }),
          })
            .then(function (res) {
              if (!res.ok) throw new Error(lang === "ar" ? "خطأ" : "Erreur");
              return res.json();
            })
            .then(function (updated) {
              localStorage.setItem(votedKey, "1");
              renderSondageExpressResults(container, updated);
            })
            .catch(function () {});
        });
      });
    })
    .catch(function () {});
}

function loadTemoignages() {
  var container = document.getElementById("temoignages-grid");
  var section = document.getElementById("temoignages-section");
  if (!container) return;

  fetch(API_BASE + "/api/temoignages")
    .then(function (res) {
      if (!res.ok) throw new Error("API indisponible");
      return res.json();
    })
    .then(function (items) {
      if (!items || !items.length) return;
      if (section) section.style.display = "";
      container.innerHTML = items
        .map(function (item) {
          var avatarInner = item.photo_url
            ? '<img src="' + API_BASE + item.photo_url + '" alt="">'
            : initialsFrom(item.auteur_nom);
          return (
            '<div class="temoignage-card">' +
            '<svg class="temoignage-quote-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9 7c-2.8 0-5 2.2-5 5v5h5v-5H6.5C6.5 9.8 7.6 8.5 9 8.2V7Zm10 0c-2.8 0-5 2.2-5 5v5h5v-5h-2.5c0-2.2 1.1-3.5 2.5-3.8V7Z"/></svg>' +
            '<p class="temoignage-text">' + escapeHtml(item.texte) + "</p>" +
            '<div class="temoignage-author">' +
            '<div class="temoignage-avatar">' + avatarInner + "</div>" +
            "<div><div class=\"temoignage-author-name\">" + escapeHtml(item.auteur_nom) + "</div>" +
            (item.auteur_role ? '<div class="temoignage-author-role">' + escapeHtml(item.auteur_role) + "</div>" : "") +
            "</div></div></div>"
          );
        })
        .join("");
    })
    .catch(function () {
      // API indisponible : rien ne s'affiche (pas de contenu de repli statique).
    });
}

function loadConseilAdministration() {
  var container = document.getElementById("conseil-administration-grid");
  if (!container) return;

  fetch(API_BASE + "/api/conseil-administration")
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
      // API indisponible : le message par défaut ("aucun membre publié") reste affiché.
    });
}

function initialsFrom(text) {
  if (!text) return "?";
  var words = text.split(/\s+/).filter(function (w) { return w.length > 1; });
  var letters = words.slice(0, 2).map(function (w) { return w.charAt(0).toUpperCase(); });
  return letters.join("") || text.charAt(0).toUpperCase();
}

function orgCardInner(item) {
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

  return (
    '<div class="org-avatar-wrap">' +
    '<div class="org-avatar">' + titulaireInner + "</div>" +
    adjointBadge +
    "</div>" +
    "<h4>" + escapeHtml(item.titulaire_nom || item.poste_title) + "</h4>" +
    "<span>" + escapeHtml(item.poste_subtitle || item.poste_title) + "</span>"
  );
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

      var lang = document.documentElement.getAttribute("lang") === "ar" ? "ar" : "fr";
      var autresTitle = lang === "ar" ? "أعضاء آخرون في المكتب" : "Autres membres du Bureau Exécutif";

      var pyramidItems = items.filter(function (i) { return i.niveau && i.niveau !== "autre"; });
      var autresItems = items.filter(function (i) { return !i.niveau || i.niveau === "autre"; });

      var byId = {};
      pyramidItems.forEach(function (i) { byId[i.id] = i; });
      var childrenOf = {};
      pyramidItems.forEach(function (i) {
        var pid = i.parent_id && byId[i.parent_id] ? i.parent_id : "__root__";
        if (!childrenOf[pid]) childrenOf[pid] = [];
        childrenOf[pid].push(i);
      });

      var NIVEAU_ORDER = { president: 0, vice_president: 1, secretariat: 2 };
      function sortNodes(arr) {
        return arr.slice().sort(function (a, b) {
          var na = NIVEAU_ORDER[a.niveau] != null ? NIVEAU_ORDER[a.niveau] : 9;
          var nb = NIVEAU_ORDER[b.niveau] != null ? NIVEAU_ORDER[b.niveau] : 9;
          if (na !== nb) return na - nb;
          return (a.ordre || 0) - (b.ordre || 0);
        });
      }

      function renderNode(item, visited) {
        if (visited.indexOf(item.id) !== -1) return "";
        var nextVisited = visited.concat([item.id]);
        var kids = sortNodes(childrenOf[item.id] || []);
        var html = '<li><div class="org-card org-card-' + item.niveau + '">' + orgCardInner(item) + "</div>";
        if (kids.length) {
          html += "<ul>" + kids.map(function (k) { return renderNode(k, nextVisited); }).join("") + "</ul>";
        }
        html += "</li>";
        return html;
      }

      var roots = sortNodes(childrenOf["__root__"] || []);
      var pyramidHtml = roots.length
        ? '<div class="orgchart-scroll"><ul class="orgchart">' +
          roots.map(function (r) { return renderNode(r, []); }).join("") +
          "</ul></div>"
        : "";

      var autresHtml = autresItems.length
        ? "<div>" +
          '<div class="gouvernance-autres-title">' + escapeHtml(autresTitle) + "</div>" +
          '<div class="org-grid">' +
          autresItems.map(function (i) { return '<div class="org-card">' + orgCardInner(i) + "</div>"; }).join("") +
          "</div></div>"
        : "";

      if (!pyramidHtml && !autresHtml) return;
      container.innerHTML = pyramidHtml + autresHtml;
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

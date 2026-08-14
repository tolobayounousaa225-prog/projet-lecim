// Service worker du site vitrine LECIM — cache l'app shell statique (CSS, JS, logo,
// icônes) pour un chargement plus rapide et plus tolérant aux connexions faibles.
// Les appels à l'API (données dynamiques, autre origine) ne sont jamais mis en cache
// ici : ils passent toujours par le réseau, pour ne jamais servir de contenu périmé.

var CACHE_NAME = "lecim-shell-v1";

var APP_SHELL = [
  "/assets/css/style.css",
  "/assets/js/script.js",
  "/assets/img/logo.jpg",
  "/assets/img/icons/icon-192.png",
  "/assets/img/icons/icon-512.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(APP_SHELL);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names
          .filter(function (name) { return name !== CACHE_NAME; })
          .map(function (name) { return caches.delete(name); })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  if (request.method !== "GET") return;

  var url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match(request).then(function (cached) {
          return cached || caches.match("/index.html");
        });
      })
    );
    return;
  }

  if (APP_SHELL.indexOf(url.pathname) !== -1) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        var network = fetch(request).then(function (response) {
          if (response.ok) {
            caches.open(CACHE_NAME).then(function (cache) { cache.put(request, response.clone()); });
          }
          return response;
        }).catch(function () { return cached; });
        return cached || network;
      })
    );
  }
});

const CACHE = "miney-v2";

// Rutas de activos estáticos: CSS, JS, iconos, manifest. Se sirven cache-first.
const STATIC_PREFIXES = ["/static/"];
const STATIC_PATHS = ["/sw.js"];

function isStatic(url) {
  return (
    STATIC_PREFIXES.some((p) => url.pathname.startsWith(p)) ||
    STATIC_PATHS.includes(url.pathname)
  );
}

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== location.origin) return;

  if (isStatic(url)) {
    // Estáticos: cache-first con revalidación en segundo plano (stale-while-revalidate).
    // Respuesta instantánea desde caché y actualización silenciosa para la próxima visita.
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request)
            .then((response) => {
              if (response.ok) cache.put(request, response.clone());
              return response;
            })
            .catch(() => cached);
          return cached || network;
        })
      )
    );
    return;
  }

  // HTML y datos dinámicos: network-first (siempre datos frescos; caché como fallback offline).
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});

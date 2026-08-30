const CACHE = "maxmin-remaster-v9-experiencia-20260830";
const APP_SHELL = [
  "./", "./index.html", "./css/styles.css", "./js/app.js", "./data/manifest.js",
  "./data/normalized/manifest.js",
  "./vendor/jspdf.umd.min.js", "./manifest.webmanifest", "./icons/icon-192.png",
  "./icons/icon-512.png", "./icons/favicon-32.png", "./icons/apple-touch-icon.png",
  "./assets/ui/Damos_Seguimiento.webp", "./assets/ui/Un_placer_haber_Ayudado.webp",
  "./assets/reference/BOH_5S_Referencia.webp", "./docs/guias/Guia_5S_BOH.pdf",
  "./docs/guias/Alineacion_acomodo_items.pdf"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  const isData = url.pathname.includes("/data/");
  if (isData) {
    event.respondWith(fetch(event.request).then((response) => {
      if (response.ok) caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
      return response;
    }).catch(() => caches.match(event.request)));
    return;
  }
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {
    if (response.ok) caches.open(CACHE).then((cache) => cache.put(event.request, response.clone()));
    return response;
  }).catch(() => caches.match("./index.html"))));
});

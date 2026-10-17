const CACHE = "maxmin-weekly-v12-20261017";
const APP_SHELL = [
  "./", "./index.html", "./css/styles.css", "./js/app.js", "./data/manifest.js",
  "./data/normalized/manifest.js", "./vendor/jspdf.umd.min.js", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/favicon-32.png", "./icons/apple-touch-icon.png",
  "./assets/ui/Damos_Seguimiento.webp", "./assets/ui/Un_placer_haber_Ayudado.webp",
  "./assets/reference/BOH_5S_Referencia.webp", "./docs/guias/Guia_5S_BOH.pdf", "./docs/guias/Alineacion_acomodo_items.pdf"
];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("maxmin-") && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
function timeout(promise, ms) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("timeout")), ms); })]).finally(() => clearTimeout(timer));
}
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  const isData = /\/data\/(?:manifest\.js|normalized\/manifest\.js|(?:normalized\/)?stores_\d+\/\d+\.json)$/.test(url.pathname);
  const isNavigation = event.request.mode === "navigate";
  const isShell = APP_SHELL.some(path => new URL(path, self.location.href).pathname === url.pathname);
  if (!isData && !isNavigation && !isShell) return;
  const network = async () => {
    const response = await fetch(event.request, {cache: "no-store"});
    if (!response.ok) throw new Error("Recurso no disponible");
    const copy = response.clone();
    event.waitUntil(caches.open(CACHE).then(async cache => {
      await cache.put(isNavigation ? "./index.html" : event.request, copy);
      if (isData) {
        const keys = (await cache.keys()).filter(key => /\/stores_\d+\/\d+\.json$/.test(new URL(key.url).pathname));
        for (const key of keys.slice(0, Math.max(0, keys.length - 200))) await cache.delete(key);
      }
    }).catch(() => {}));
    return response;
  };
  event.respondWith((async () => {
    const cached = await caches.match(event.request);
    if (cached && !isData && !isNavigation) return cached;
    try { return await timeout(network(), 2500); }
    catch { return cached || (isNavigation && await caches.match("./index.html")) || Response.error(); }
  })());
});

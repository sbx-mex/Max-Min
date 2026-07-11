const CACHE_NAME = 'maxmin-pwa-v31-visual-slicers';

const APP_SHELL = [
  "./",
  "./index.html",
  "./css/styles.css",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png",
  "./icons/hero-maxmin.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/splash-1920x1080.png",
  "./js/app.js",
  "./js/data_index.js",
  "./js/data_sem_18.js",
  "./js/data_sem_19.js",
  "./js/data_sem_20.js",
  "./js/data_sem_21.js",
  "./js/data_sem_22.js",
  "./js/data_sem_23.js",
  "./js/data_sem_24.js",
  "./js/data_sem_25.js",
  "./manifest.webmanifest"
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => Promise.allSettled(APP_SHELL.map(url => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;

      return fetch(event.request).then(response => {
        if (response && response.ok && new URL(event.request.url).origin === self.location.origin) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }
        return response;
      }).catch(() => caches.match('./index.html'));
    })
  );
});

const CACHE = "supra-cosmos-v0.4.0";
const LOCAL_ASSETS = [
  "./", "./index.html", "./styles.css", "./app.mjs", "./core.mjs", "./worker.mjs",
  "./manifest.webmanifest", "./icon.svg", "./xr-lab.html", "./xr-lab.css", "./xr-lab.mjs"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(LOCAL_ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  })));
});

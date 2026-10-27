/* Service worker: makes the static build installable and playable with no network.
   tools/build_web.py fills in VERSION and FILES (every file of dist/); in a plain `serve.py` checkout FILES is empty and
   the worker stays out of the way. The big Python runtime (vendor/) is served from the cache first - it never changes within a
   version. Everything else (the page, scripts, the game) comes from the network first and the cache only when offline, so a
   phone never runs an old page against new files. A new VERSION replaces the old cache on the next visit. */
const VERSION = '__VERSION__';
const FILES = __FILES__;
const CACHE = 'slimegacha-' + VERSION;

self.addEventListener('install', (e) => {
  if (!FILES.length) return;
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k.startsWith('slimegacha-') && k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', (e) => {
  if (!FILES.length || e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes('/vendor/')) {                  // cache first: the runtime is fixed for this version
    e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request)));
    return;
  }
  e.respondWith(fetch(e.request).then((r) => {             // network first: always the current page and game
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {}); }
    return r;
  }).catch(() => caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || Response.error())));
});

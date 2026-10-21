/* Service worker: makes the static build installable and playable with no network.
   tools/build_web.py fills in VERSION and FILES (every file of dist/); in a plain `serve.py` checkout FILES is empty and
   the worker stays out of the way. Pages are cache-first; a new VERSION replaces the old cache on the next visit. */
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
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request)));
});

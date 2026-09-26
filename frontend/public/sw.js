const CACHE = 'tickvendor-shell-v6';
const CACHE_PREFIX = 'tickvendor-shell-';
const LEGACY_CACHE_PREFIX = 'tickeven-shell-';
const SAFE_API = ['/api/v1/events'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE)
      .then(cache => cache.addAll(['/manifest.webmanifest']))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => (
            key.startsWith(CACHE_PREFIX) || key.startsWith(LEGACY_CACHE_PREFIX)
          ) && key !== CACHE)
          .map(key => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

async function networkFirst(request, fallback) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch {
    return (await cache.match(request)) || (fallback ? await cache.match(fallback) : undefined);
  }
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  const safeApi = SAFE_API.some(path => url.pathname === path || url.pathname.startsWith(`${path}/`));
  if (safeApi) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Never intercept authenticated or mutating API traffic. In particular, an application route
  // must not turn a relative API request into the static site's index.html with a misleading 200.
  if (url.pathname.startsWith('/api/')) return;

  // HTML navigation must be network-first so a deployment cannot leave visitors running an old
  // index that points at retired hashed bundles. The cached shell remains an offline fallback.
  if (event.request.mode === 'navigate') {
    event.respondWith(networkFirst(event.request, '/'));
    return;
  }

  // Built assets are content-hashed and can safely remain cache-first.
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy)));
      }
      return response;
    })),
  );
});

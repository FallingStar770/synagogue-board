/* Offline-first service worker for the TV display.
 * - install: precaches the whole built app (list from precache-manifest.json)
 * - navigation: network-first (3s timeout) → cached index.html when offline
 * - built assets/fonts: cache-first
 * - /api/v1/media/*: cache-first (images needed offline, e.g. tzadik portraits / logo)
 * - other /api requests: network only (the app keeps its own verified snapshot in IndexedDB)
 */
const SHELL_PREFIX = 'sdb-shell-'
const MEDIA_CACHE = 'sdb-media-v1'
const scopeUrl = new URL(self.registration.scope)

async function manifest() {
  const res = await fetch(new URL('precache-manifest.json', scopeUrl), { cache: 'no-store' })
  if (!res.ok) throw new Error('manifest unavailable')
  return res.json()
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const m = await manifest()
    const cache = await caches.open(SHELL_PREFIX + m.version)
    await cache.addAll(m.files.map(f => new Request(new URL(f, scopeUrl), { cache: 'reload' })))
    await self.skipWaiting()
  })())
})

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    let current = null
    try { current = SHELL_PREFIX + (await manifest()).version } catch { /* offline: keep everything */ }
    if (current) {
      for (const key of await caches.keys()) if (key.startsWith(SHELL_PREFIX) && key !== current) await caches.delete(key)
    }
    await self.clients.claim()
  })())
})

async function shellMatch(request) {
  const keys = (await caches.keys()).filter(k => k.startsWith(SHELL_PREFIX)).reverse()
  for (const k of keys) {
    const hit = await (await caches.open(k)).match(request, { ignoreSearch: true })
    if (hit) return hit
  }
  return undefined
}

function timeout(ms) { return new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms)) }

self.addEventListener('fetch', event => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== location.origin) return

  if (url.pathname.includes('/api/v1/media/')) {
    event.respondWith((async () => {
      const cache = await caches.open(MEDIA_CACHE)
      const hit = await cache.match(req, { ignoreSearch: true })
      if (hit) return hit
      const res = await fetch(req)
      if (res.ok) cache.put(req, res.clone())
      return res
    })())
    return
  }
  if (url.pathname.includes('/api/')) return // app-level offline handling

  if (req.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const res = await Promise.race([fetch(req), timeout(3000)])
        if (res && res.ok) return res
        throw new Error('bad response')
      } catch {
        return (await shellMatch(new URL('./index.html', scopeUrl).href)) || (await shellMatch(new URL('./', scopeUrl).href)) ||
          new Response('<h1 dir="rtl">אין חיבור והאפליקציה עדיין לא נשמרה במכשיר</h1>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } })
      }
    })())
    return
  }
  if (url.pathname.startsWith(scopeUrl.pathname)) {
    event.respondWith((async () => (await shellMatch(req)) || fetch(req))())
  }
})

self.addEventListener('message', event => {
  if (event.data?.type === 'cache-media' && Array.isArray(event.data.urls)) {
    event.waitUntil((async () => {
      const cache = await caches.open(MEDIA_CACHE)
      for (const u of event.data.urls) {
        try {
          if (!(await cache.match(u))) { const r = await fetch(u); if (r.ok) await cache.put(u, r) }
        } catch { /* will retry on next sync */ }
      }
      // drop media that is no longer referenced
      const keep = new Set(event.data.urls.map(u => new URL(u, scopeUrl).href))
      for (const r of await cache.keys()) if (!keep.has(r.url)) await cache.delete(r)
    })())
  }
})

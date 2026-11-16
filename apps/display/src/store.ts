// Offline snapshot storage (IndexedDB, localStorage fallback) + sync engine.
import { sha256Text } from './sha256'
import type { Snapshot } from './logic'

const DB = 'synagogue-display'
const STORE = 'kv'
type Saved = { version: number; checksum: string; text: string; saved_at: string }

function openDb(): Promise<IDBDatabase | null> {
  return new Promise(resolve => {
    try {
      const r = indexedDB.open(DB, 1)
      r.onupgradeneeded = () => r.result.createObjectStore(STORE)
      r.onsuccess = () => resolve(r.result)
      r.onerror = () => resolve(null)
    } catch { resolve(null) }
  })
}

export async function kvGet<T>(key: string): Promise<T | undefined> {
  const db = await openDb()
  if (!db) { const v = localStorage.getItem('sdb:' + key); return v ? JSON.parse(v) : undefined }
  return new Promise(resolve => {
    const tx = db.transaction(STORE, 'readonly')
    const r = tx.objectStore(STORE).get(key)
    r.onsuccess = () => resolve(r.result as T)
    r.onerror = () => resolve(undefined)
  })
}

export async function kvSet(entries: Record<string, unknown>): Promise<void> {
  const db = await openDb()
  if (!db) { for (const [k, v] of Object.entries(entries)) localStorage.setItem('sdb:' + k, JSON.stringify(v)); return }
  // one transaction → all keys are replaced atomically (no half-written snapshot)
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    for (const [k, v] of Object.entries(entries)) tx.objectStore(STORE).put(v, k)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error)
  })
}

export function validateSnapshot(s: any): s is Snapshot {
  return s && s.schema === 1 && typeof s.days === 'object' && Array.isArray(s.screens) && s.settings && typeof s.local_date === 'string'
}

export type SyncState = { online: boolean; lastSync: string | null; lastError: string | null; version: number | null }

export class SyncEngine {
  private token: string | null
  private preview: boolean
  private timer: ReturnType<typeof setTimeout> | null = null
  private failures = 0
  current: Saved | null = null
  state: SyncState = { online: navigator.onLine, lastSync: null, lastError: null, version: null }
  onSnapshot: (s: Snapshot) => void = () => {}
  onState: (s: SyncState) => void = () => {}
  currentScreen = ''

  constructor(token: string | null, preview: boolean) {
    this.token = token
    this.preview = preview
  }

  private headers(): HeadersInit {
    return this.token ? { Authorization: `Bearer ${this.token}` } : {}
  }

  private key(k: string) { return this.preview ? 'preview:' + k : k }

  /** Load the last verified snapshot from the device; falls back to the previous good one. */
  async loadLocal(): Promise<Snapshot | null> {
    for (const k of ['current', 'previous']) {
      const saved = await kvGet<Saved>(this.key(k))
      if (!saved) continue
      try {
        if (sha256Text(saved.text) !== saved.checksum) continue // corrupted → try previous
        const snap = JSON.parse(saved.text)
        if (!validateSnapshot(snap)) continue
        this.current = saved
        this.state = { ...this.state, version: saved.version, lastSync: saved.saved_at }
        this.cacheMedia(snap.media || [])
        return snap
      } catch { /* try previous */ }
    }
    return null
  }

  private setState(p: Partial<SyncState>) {
    this.state = { ...this.state, ...p }
    this.onState(this.state)
  }

  async syncOnce(): Promise<boolean> {
    const vres = await fetch('/api/v1/display/version', { headers: this.headers(), cache: 'no-store', credentials: 'same-origin' })
    if (vres.status === 401) throw new Error('unauthorized')
    if (!vres.ok) throw new Error('version ' + vres.status)
    const v = await vres.json()
    if (this.current && this.current.version === v.version && this.current.checksum === v.checksum) {
      this.setState({ online: true, lastError: null, lastSync: new Date().toISOString() })
      this.cacheMedia(this.mediaOf()) // retry any image that failed to cache earlier
      return false
    }
    const res = await fetch('/api/v1/display/snapshot', { headers: this.headers(), cache: 'no-store', credentials: 'same-origin' })
    if (!res.ok) throw new Error('snapshot ' + res.status)
    const text = await res.text() // a network drop mid-download throws here → old data stays
    const expected = res.headers.get('X-Snapshot-Checksum') || v.checksum
    const actual = sha256Text(text)
    if (actual !== expected) throw new Error('checksum mismatch')
    const snap = JSON.parse(text)
    if (!validateSnapshot(snap)) throw new Error('invalid snapshot')
    const version = Number(res.headers.get('X-Snapshot-Version') || v.version)
    const saved: Saved = { version, checksum: actual, text, saved_at: new Date().toISOString() }
    const entries: Record<string, unknown> = { [this.key('current')]: saved }
    if (this.current) entries[this.key('previous')] = this.current
    await kvSet(entries) // atomic swap; render only after it is safely stored
    this.current = saved
    this.cacheMedia(snap.media || [])
    this.onSnapshot(snap)
    this.setState({ online: true, lastError: null, lastSync: saved.saved_at, version })
    return true
  }

  /** Ask the service worker to keep every image the snapshot needs (works before the SW
   * controls the page, via registration.active). Already-cached files are skipped. */
  cacheMedia(urls: string[]) {
    if (!('serviceWorker' in navigator)) return
    const resolved = urls.map(u => new URL(u, location.origin).href)
    navigator.serviceWorker.ready.then(reg => reg.active?.postMessage({ type: 'cache-media', urls: resolved })).catch(() => {})
  }

  private mediaOf(): string[] {
    try { return this.current ? JSON.parse(this.current.text).media || [] : [] } catch { return [] }
  }

  async heartbeat() {
    if (!this.token) return
    try {
      await fetch('/api/v1/devices/heartbeat', {
        method: 'POST', headers: { ...this.headers(), 'Content-Type': 'application/json' }, cache: 'no-store',
        body: JSON.stringify({ snapshot_version: this.state.version, online: this.state.online, current_screen: this.currentScreen.slice(0, 120),
          app_version: '1.0.0', screen_size: `${screen.width}x${screen.height}`, errors: this.state.lastError ? [this.state.lastError] : [] }),
      })
    } catch { /* offline */ }
  }

  start(intervalMs = 60_000) {
    const loop = async () => {
      let delay = intervalMs
      try {
        await this.syncOnce()
        this.failures = 0
      } catch (e) {
        this.failures++
        const msg = (e as Error).message
        this.setState({ online: false, lastError: msg })
        if (msg === 'unauthorized') delay = 5 * 60_000
        else delay = Math.min(15_000 * 2 ** (this.failures - 1), 5 * 60_000) * (0.8 + Math.random() * 0.4) // backoff + jitter
      }
      void this.heartbeat()
      this.timer = setTimeout(loop, delay)
    }
    window.addEventListener('online', () => { if (this.timer) clearTimeout(this.timer); this.failures = 0; void loop() })
    window.addEventListener('offline', () => this.setState({ online: false }))
    void loop()
  }
}

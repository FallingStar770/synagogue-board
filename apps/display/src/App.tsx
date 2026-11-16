import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { dayContext, hasContent, playlist, sponsorsFor, dedicationText, type PlaylistItem, type Snapshot, type Tzadik } from './logic'
import { HilulaView, SCREENS } from './screens'
import { SyncEngine, kvGet, kvSet, type SyncState } from './store'

const STAGE_W = 1920, STAGE_H = 1080
const params = new URLSearchParams(location.search)
const PREVIEW = params.get('preview') === '1'
const ONLY_SCREEN = params.get('screen')
const HILULA_ID = params.get('hilula')
const LAYOUT = (params.get('layout') || 'auto') as 'auto' | 'image' | 'noimage'

function useStageScale() {
  const [scale, setScale] = useState(1)
  useLayoutEffect(() => {
    const f = () => setScale(Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H))
    f()
    window.addEventListener('resize', f)
    return () => window.removeEventListener('resize', f)
  }, [])
  return scale
}

function useNow() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    // align ticks to the second; uses the device clock, so it keeps running with no network
    let t: ReturnType<typeof setTimeout>
    const tick = () => { setNow(new Date()); t = setTimeout(tick, 1000 - (Date.now() % 1000) + 5) }
    tick()
    return () => clearTimeout(t)
  }, [])
  return now
}

async function resolveToken(): Promise<string | null> {
  const hash = new URLSearchParams(location.hash.slice(1))
  const fromUrl = hash.get('pair') || params.get('token')
  if (fromUrl && /^dev_[A-Za-z0-9_-]{20,}$/.test(fromUrl)) {
    await kvSet({ device_token: fromUrl })
    try { localStorage.setItem('sdb:device_token', JSON.stringify(fromUrl)) } catch { /* ignore */ }
    params.delete('token')
    history.replaceState(null, '', location.pathname + (params.toString() ? '?' + params : '')) // remove secret from URL
    return fromUrl
  }
  return (await kvGet<string>('device_token')) || null
}

function Stage({ children, theme }: { children: React.ReactNode; theme?: Record<string, any> }) {
  const scale = useStageScale()
  const style = {
    width: STAGE_W, height: STAGE_H, transform: `translate(-50%, -50%) scale(${scale})`,
    '--primary': theme?.primary || '#14304a', '--accent': theme?.accent || '#c9a45c', '--fs': theme?.font_scale || 1,
  } as React.CSSProperties
  return <div className={'stage bg-' + (theme?.background || 'night')} style={style}>{children}</div>
}

function BigClock({ now, note }: { now: Date; note: React.ReactNode }) {
  const t = now.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit', hour12: false })
  return (
    <Stage>
      <div className="maintenance">
        <div className="m-time">{t}</div>
        <div className="m-note">{note}</div>
      </div>
    </Stage>
  )
}

function Header({ snap, ctx }: { snap: Snapshot; ctx: ReturnType<typeof dayContext> }) {
  return (
    <header className="ribbon">
      <div className="rib-side right">{ctx.hebrewLabel}{ctx.holiday && <small>{ctx.holiday}</small>}</div>
      <div className="rib-center"><div className="rib-name">{snap.settings.name}</div><div className="rib-clock">{ctx.time}<span>{ctx.seconds}</span></div></div>
      <div className="rib-side left">{ctx.day?.parsha ? <>פרשת<br /><b>{ctx.day.parsha}</b></> : ''}</div>
    </header>
  )
}

function Footer({ snap, ctx, sync }: { snap: Snapshot; ctx: ReturnType<typeof dayContext>; sync: SyncState }) {
  const items = useMemo(() => {
    const s = sponsorsFor(snap, ctx).filter(x => x.footer).map(dedicationText)
    return s.length ? s : snap.settings.footer_text ? [snap.settings.footer_text] : []
  }, [snap, ctx.date])
  const [i, setI] = useState(0)
  useEffect(() => { const t = setInterval(() => setI(x => x + 1), 9000); return () => clearInterval(t) }, [])
  return (
    <footer className="plaque-row">
      {items.length > 0 && <div className="plaque" key={i % items.length}>{items[i % items.length]}</div>}
      {!sync.online && !PREVIEW && <div className="offline" title={sync.lastError || ''}>● מצב לא מקוון — מוצגים הנתונים האחרונים שנשמרו{sync.lastSync ? ` (${new Date(sync.lastSync).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' })})` : ''}</div>}
      {PREVIEW && <div className="preview-tag">תצוגה מקדימה</div>}
    </footer>
  )
}

function toTzadik(t: any): Tzadik {
  const d = t.dates?.[0]
  return { ...t, death_year_str: null, hilula_date_str: d?.hebrew_date_str || '' }
}

export default function App() {
  const now = useNow()
  const [snap, setSnap] = useState<Snapshot | null>(null)
  const [ready, setReady] = useState(false)
  const [token, setToken] = useState<string | null | undefined>(undefined)
  const [sync, setSync] = useState<SyncState>({ online: navigator.onLine, lastSync: null, lastError: null, version: null })
  const [hilulaPreview, setHilulaPreview] = useState<Tzadik | null>(null)
  const engine = useRef<SyncEngine | null>(null)

  useEffect(() => {
    (async () => {
      const tok = PREVIEW ? null : await resolveToken()
      setToken(tok)
      if (!PREVIEW && !tok) { setReady(true); return }
      const e = new SyncEngine(tok, PREVIEW)
      engine.current = e
      e.onSnapshot = setSnap
      e.onState = setSync
      const local = await e.loadLocal() // show the last good data immediately (works offline)
      if (local) { setSnap(local); setSync(e.state) }
      setReady(true)
      e.start(PREVIEW ? 15_000 : 60_000)
      if (HILULA_ID) {
        try { const r = await fetch(`/api/v1/hilulot/${HILULA_ID}`, { credentials: 'same-origin' }); if (r.ok) setHilulaPreview(toTzadik(await r.json())) } catch { /* ignore */ }
      }
    })()
  }, [])

  const ctx = useMemo(() => (snap ? dayContext(snap, now) : null), [snap, now])

  // ---------------------------------------------------------------- playlist
  const items: PlaylistItem[] = useMemo(() => {
    if (!snap || !ctx) return []
    if (ONLY_SCREEN) {
      const s = snap.screens.find(x => x.id === ONLY_SCREEN)
      return s ? [{ screen: s, fallback: !hasContent(snap, ctx, s) }] : []
    }
    return playlist(snap, ctx)
  }, [snap, ctx?.date, ctx?.minutes, ctx?.inShabbat, ctx?.afterDayChange])
  const [curId, setCurId] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState(Date.now())
  const cur = items.find(x => x.screen.id === curId) || items[0]
  const durationMs = (cur?.screen.duration_seconds || 20) * 1000
  useEffect(() => {
    if (!items.length) return
    if (!cur || cur.screen.id !== curId) { setCurId(items[0].screen.id); setStartedAt(Date.now()); return }
    if (Date.now() - startedAt >= durationMs && items.length > 1) {
      const idx = items.findIndex(x => x.screen.id === curId)
      setCurId(items[(idx + 1) % items.length].screen.id)
      setStartedAt(Date.now())
    }
  }, [now, items])
  useEffect(() => { if (engine.current && cur) engine.current.currentScreen = cur.screen.name }, [cur?.screen.id])

  // ---------------------------------------------------------------- kiosk helpers
  useEffect(() => {
    let lock: any = null
    const req = async () => { try { lock = await (navigator as any).wakeLock?.request('screen') } catch { /* unsupported */ } }
    void req()
    const vis = () => { if (document.visibilityState === 'visible') void req() }
    document.addEventListener('visibilitychange', vis)
    const dbl = () => { if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {}); else document.exitFullscreen?.() }
    window.addEventListener('dblclick', dbl)
    return () => { document.removeEventListener('visibilitychange', vis); window.removeEventListener('dblclick', dbl); lock?.release?.() }
  }, [])
  useEffect(() => {
    // daily refresh at ~03:00 when online (new app versions, memory hygiene); never when offline
    const t = setInterval(() => { const d = new Date(); if (d.getHours() === 3 && d.getMinutes() === 0 && navigator.onLine && !PREVIEW) location.reload() }, 60_000)
    return () => clearInterval(t)
  }, [])

  // ---------------------------------------------------------------- render
  if (!ready || token === undefined) return <Stage><div className="maintenance" /></Stage>
  if (!PREVIEW && !token) {
    return <BigClock now={now} note={<><h1>המסך אינו מצומד</h1><p>במחשב המנהל: "מסכי טלוויזיה" ← "יצירת קוד התקן", ופתחו כאן את כתובת הצימוד.</p></>} />
  }
  if (!snap || !ctx) {
    return <BigClock now={now} note={<><h1>ממתין לסנכרון ראשוני…</h1><p>{sync.lastError === 'unauthorized' ? 'קוד ההתקן בוטל או שגוי — יש לצמד מחדש.' : 'נדרש חיבור לאינטרנט פעם אחת לטעינת הנתונים. לאחר מכן הלוח יעבוד גם ללא רשת.'}</p></>} />
  }
  if (HILULA_ID) {
    return (
      <Stage theme={snap.settings.theme}>
        <Header snap={snap} ctx={ctx} />
        <main className="content">{hilulaPreview ? <HilulaView t={hilulaPreview} layout={LAYOUT} /> : <div className="empty-screen">טוען…</div>}</main>
        <Footer snap={snap} ctx={ctx} sync={sync} />
      </Stage>
    )
  }
  const Comp = cur ? SCREENS[cur.screen.type] : null
  const elapsed = Math.min(1, (Date.now() - startedAt) / durationMs)
  return (
    <Stage theme={snap.settings.theme}>
      {cur?.screen.type !== 'clock' && <Header snap={snap} ctx={ctx} />}
      <main className={'content t-' + (cur?.screen.type || 'none')} key={cur?.screen.id || 'none'}>
        {!cur ? <div className="empty-screen">{ctx.expired ? 'נתוני לוח השנה לתאריך זה אינם זמינים — נדרש חיבור לעדכון' : 'אין מסכים פעילים להצגה כעת'}</div>
          : cur.fallback ? <div className="empty-screen">{cur.screen.fallback_text || 'אין תוכן להצגה כעת'}</div>
            : Comp && <Comp snap={snap} ctx={ctx} screen={cur.screen} durationMs={durationMs} />}
      </main>
      <Footer snap={snap} ctx={ctx} sync={sync} />
      {items.length > 1 && <div className="progress" style={{ transform: `scaleX(${elapsed})` }} />}
    </Stage>
  )
}

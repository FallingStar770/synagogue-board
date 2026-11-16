import '@fontsource/heebo/400.css'
import '@fontsource/heebo/500.css'
import '@fontsource/heebo/700.css'
import './styles.css'
import React, { createContext, lazy, Suspense, useContext, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'
import { HashRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ApiError, get, post, setCsrf } from './api'
import { Icon, Loading, ToastProvider } from './ui'
import Login from './pages/Login'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const DisplayPreview = lazy(() => import('./pages/DisplayPreview'))
const Screens = lazy(() => import('./pages/Screens'))
const Announcements = lazy(() => import('./pages/Announcements'))
const Prayers = lazy(() => import('./pages/Prayers'))
const Lessons = lazy(() => import('./pages/Lessons'))
const Zmanim = lazy(() => import('./pages/Zmanim'))
const Halachot = lazy(() => import('./pages/Halachot'))
const Memorials = lazy(() => import('./pages/Memorials'))
const Sponsorships = lazy(() => import('./pages/Sponsorships'))
const Hilulot = lazy(() => import('./pages/Hilulot'))
const Birthdays = lazy(() => import('./pages/Birthdays'))
const Content = lazy(() => import('./pages/Content'))
const Devices = lazy(() => import('./pages/Devices'))
const Maintenance = lazy(() => import('./pages/Maintenance'))
const Settings = lazy(() => import('./pages/Settings'))
const Users = lazy(() => import('./pages/Users'))
const Account = lazy(() => import('./pages/Account'))

export type Me = { id: string; username: string; display_name: string; role: 'admin' | 'editor'; must_change_password: boolean }
const AuthCtx = createContext<{ me: Me; logout: () => void }>(null as any)
export const useAuth = () => useContext(AuthCtx)

const NAV: { to: string; label: string; icon: string; admin?: boolean }[] = [
  { to: '/', label: 'לוח בקרה', icon: 'home' },
  { to: '/display', label: 'תצוגה', icon: 'eye' },
  { to: '/screens', label: 'מסכים', icon: 'screens' },
  { to: '/announcements', label: 'הודעות', icon: 'mail' },
  { to: '/prayers', label: 'זמני תפילות', icon: 'clock' },
  { to: '/lessons', label: 'שיעורים', icon: 'book' },
  { to: '/memorials', label: 'עילוי נשמת', icon: 'candle' },
  { to: '/zmanim', label: 'זמני היום', icon: 'sun' },
  { to: '/halachot', label: 'הלכות', icon: 'scroll' },
  { to: '/sponsorships', label: 'פרנסים', icon: 'coins' },
  { to: '/hilulot', label: 'ימי הילולה', icon: 'star' },
  { to: '/birthdays', label: 'ימי הולדת', icon: 'cake' },
  { to: '/content', label: 'תוכן תורני', icon: 'text' },
  { to: '/devices', label: 'מסכי טלוויזיה', icon: 'tv', admin: true },
  { to: '/maintenance', label: 'תחזוקה וגיבוי', icon: 'tools', admin: true },
  { to: '/users', label: 'משתמשים', icon: 'users', admin: true },
  { to: '/settings', label: 'הגדרות כלליות', icon: 'gear' },
]

function Shell({ me, onLogout }: { me: Me; onLogout: () => void }) {
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => get('/settings') })
  useEffect(() => setOpen(false), [loc.pathname])
  const current = NAV.find(n => n.to === loc.pathname)?.label || ''
  useEffect(() => { document.title = `${current ? current + ' · ' : ''}ניהול לוח בית הכנסת` }, [current])
  return (
    <AuthCtx.Provider value={{ me, logout: onLogout }}>
      <a href="#main" className="skip">דילוג לתוכן</a>
      <div className={'shell' + (open ? ' nav-open' : '')}>
        <aside className="sidebar" aria-label="תפריט ראשי">
          <div className="brand">
            <div className="logo-mark"><Icon name="star" size={22} /></div>
            <div><strong>{settings?.name || 'בית הכנסת'}</strong><small>לוח דיגיטלי</small></div>
          </div>
          <nav>
            {NAV.filter(n => !n.admin || me.role === 'admin').map(n => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
                <Icon name={n.icon} /><span>{n.label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            <NavLink to="/account" className="user"><Icon name="key" size={18} /><span>שלום {me.display_name || me.username}</span></NavLink>
            <button type="button" className="logout" onClick={onLogout}><Icon name="logout" size={18} />התנתקות</button>
          </div>
        </aside>
        <div className="scrim" onClick={() => setOpen(false)} />
        <div className="main-col">
          <header className="topbar">
            <button type="button" className="icon-btn menu-btn" aria-label="פתיחת תפריט" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name="menu" /></button>
            <span className="topbar-title">{current}</span>
            <a className="btn ghost small" href="../display/?preview=1" target="_blank" rel="noopener"><Icon name="eye" size={18} />פתיחת התצוגה</a>
          </header>
          <main id="main" tabIndex={-1}>
            {me.must_change_password && loc.pathname !== '/account' && (
              <div className="banner warn"><Icon name="alert" /> מומלץ להחליף את הסיסמה הראשונית. <NavLink to="/account">להחלפת סיסמה</NavLink></div>
            )}
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/display" element={<DisplayPreview />} />
                <Route path="/screens" element={<Screens />} />
                <Route path="/announcements" element={<Announcements />} />
                <Route path="/prayers" element={<Prayers />} />
                <Route path="/lessons" element={<Lessons />} />
                <Route path="/zmanim" element={<Zmanim />} />
                <Route path="/halachot" element={<Halachot />} />
                <Route path="/memorials" element={<Memorials />} />
                <Route path="/sponsorships" element={<Sponsorships />} />
                <Route path="/hilulot" element={<Hilulot />} />
                <Route path="/birthdays" element={<Birthdays />} />
                <Route path="/content" element={<Content />} />
                <Route path="/devices" element={<Devices />} />
                <Route path="/maintenance" element={<Maintenance />} />
                <Route path="/users" element={<Users />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/account" element={<Account />} />
                <Route path="*" element={<Navigate to="/" />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    </AuthCtx.Provider>
  )
}

function App() {
  const qc = useQueryClient()
  const [me, setMe] = useState<Me | null | undefined>(undefined)
  const load = async () => {
    try {
      const r = await get('/auth/me')
      setCsrf(r.csrf_token)
      setMe(r.user)
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null)
      else setMe(null)
    }
  }
  useEffect(() => {
    void load()
    const onExpired = () => { setMe(null); qc.clear() }
    window.addEventListener('auth:expired', onExpired)
    return () => window.removeEventListener('auth:expired', onExpired)
  }, [])
  const logout = async () => {
    try { await post('/auth/logout') } catch { /* already out */ }
    qc.clear()
    setMe(null)
  }
  if (me === undefined) return <Loading />
  if (me === null) return <Login onLogin={(u, csrf) => { setCsrf(csrf); setMe(u) }} />
  return <Shell me={me} onLogout={logout} />
}

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 } } })
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <HashRouter><App /></HashRouter>
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)

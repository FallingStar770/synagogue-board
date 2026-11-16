import { useState } from 'react'
import { post } from '../api'
import { Icon } from '../ui'
import type { Me } from '../main'

export default function Login({ onLogin }: { onLogin: (u: Me, csrf: string) => void }) {
  const [username, setU] = useState('')
  const [password, setP] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await post('/auth/login', { username, password })
      onLogin(r.user, r.csrf_token)
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit} aria-labelledby="login-title">
        <div className="logo-mark big"><Icon name="star" size={34} /></div>
        <h1 id="login-title">ניהול לוח בית הכנסת</h1>
        <p className="muted">התחברות למנהלי המערכת</p>
        <label>שם משתמש<input autoComplete="username" value={username} onChange={e => setU(e.target.value)} required autoFocus /></label>
        <label>סיסמה<input type="password" autoComplete="current-password" value={password} onChange={e => setP(e.target.value)} required /></label>
        {error && <div className="error-box" role="alert">{error}</div>}
        <button className="btn primary block" disabled={busy}>{busy ? 'מתחבר…' : 'כניסה'}</button>
        <small className="muted">החיבור מאובטח בעוגייה מוגנת. לטלוויזיה יש קוד התקן נפרד — אין להזין בה סיסמת מנהל.</small>
      </form>
    </div>
  )
}

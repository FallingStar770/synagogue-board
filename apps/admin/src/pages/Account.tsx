import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, get, post } from '../api'
import { useAuth } from '../main'
import { Btn, Card, ErrorBox, Field, PageHeader, fmtDateTime, useToast } from '../ui'

export default function Account() {
  const { me } = useAuth()
  const toast = useToast()
  const qc = useQueryClient()
  const [cur, setCur] = useState('')
  const [pw, setPw] = useState('')
  const [pw2, setPw2] = useState('')
  const [err, setErr] = useState<unknown>(null)
  const sessions = useQuery<any[]>({ queryKey: ['sessions'], queryFn: () => get('/auth/sessions') })
  const change = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null)
    if (pw !== pw2) return setErr(new Error('הסיסמאות אינן תואמות'))
    try { await post('/auth/change-password', { current_password: cur, new_password: pw }); toast('הסיסמה עודכנה. שאר החיבורים נותקו.'); setCur(''); setPw(''); setPw2(''); setTimeout(() => location.reload(), 1200) } catch (e2) { setErr(e2) }
  }
  return (
    <div>
      <PageHeader title="החשבון שלי" subtitle={`${me.display_name || me.username} · ${me.role === 'admin' ? 'מנהל' : 'עורך'}`} />
      <div className="dash-grid">
        <Card title="החלפת סיסמה">
          <form onSubmit={change}>
            <ErrorBox error={err} />
            <Field label="סיסמה נוכחית"><input type="password" autoComplete="current-password" value={cur} onChange={e => setCur(e.target.value)} required /></Field>
            <Field label="סיסמה חדשה" hint="לפחות 10 תווים, שילוב אותיות וספרות"><input type="password" autoComplete="new-password" value={pw} onChange={e => setPw(e.target.value)} required minLength={10} /></Field>
            <Field label="אימות סיסמה"><input type="password" autoComplete="new-password" value={pw2} onChange={e => setPw2(e.target.value)} required /></Field>
            <button className="btn primary">עדכון סיסמה</button>
          </form>
        </Card>
        <Card title="חיבורים פעילים">
          <ul className="mini-list">{sessions.data?.map(s => (
            <li key={s.id}><span><strong>{s.current ? 'החיבור הנוכחי' : s.ip}</strong><br /><small className="muted">{s.user_agent?.slice(0, 60)} · {fmtDateTime(s.last_seen_at)}</small></span>
              {!s.current && <Btn kind="ghost" onClick={async () => { await del(`/auth/sessions/${s.id}`); qc.invalidateQueries({ queryKey: ['sessions'] }) }}>ניתוק</Btn>}</li>
          ))}</ul>
        </Card>
      </div>
    </div>
  )
}

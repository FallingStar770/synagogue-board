import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, get, patch, post } from '../api'
import { useAuth } from '../main'
import { Badge, Btn, Card, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Select, Toggle, fmtDateTime, useConfirm, useToast } from '../ui'

export default function Users() {
  const { me } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const { data = [], isLoading } = useQuery<any[]>({ queryKey: ['users'], queryFn: () => get('/users') })
  const [form, setForm] = useState<any>(null)
  const [err, setErr] = useState<unknown>(null)
  const save = async () => {
    setErr(null)
    try {
      if (form.id) await patch(`/users/${form.id}`, { display_name: form.display_name, role: form.role, is_active: form.is_active, ...(form.password ? { password: form.password } : {}) })
      else await post('/users', { username: form.username, display_name: form.display_name, role: form.role, password: form.password })
      qc.invalidateQueries({ queryKey: ['users'] }); setForm(null); toast('נשמר')
    } catch (e) { setErr(e) }
  }
  return (
    <div>
      <PageHeader title="משתמשים" subtitle="מנהלים (גישה מלאה) ועורכים (עריכת תוכן בלבד)" actions={<Btn kind="primary" icon="plus" onClick={() => setForm({ username: '', display_name: '', role: 'editor', password: '', is_active: true })}>משתמש חדש</Btn>} />
      {dialog}
      <Card>
        {isLoading ? <Loading /> : <div className="table-wrap"><table>
          <thead><tr><th>שם משתמש</th><th>שם תצוגה</th><th>תפקיד</th><th>התחברות אחרונה</th><th>מצב</th><th></th></tr></thead>
          <tbody>{data.map(u => (
            <tr key={u.id} className={u.is_active ? '' : 'disabled'}>
              <td dir="ltr" className="ltr-cell">{u.username}</td><td>{u.display_name}</td><td>{u.role === 'admin' ? <Badge tone="gold">מנהל</Badge> : <Badge>עורך</Badge>}</td>
              <td>{fmtDateTime(u.last_login_at)}</td><td>{u.is_active ? 'פעיל' : 'מושבת'}</td>
              <td className="row-actions">
                <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setForm({ ...u, password: '' })}><Icon name="edit" size={18} /></button>
                {u.id !== me.id && <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm(`למחוק את ${u.username}?`)) { try { await del(`/users/${u.id}`); qc.invalidateQueries({ queryKey: ['users'] }) } catch (e) { toast((e as Error).message, 'error') } } }}><Icon name="trash" size={18} /></button>}
              </td>
            </tr>))}</tbody>
        </table></div>}
      </Card>
      {form && (
        <Modal title={form.id ? `עריכת ${form.username}` : 'משתמש חדש'} onClose={() => setForm(null)} footer={<><Btn kind="primary" onClick={save}>שמירה</Btn><Btn onClick={() => setForm(null)}>ביטול</Btn></>}>
          <ErrorBox error={err} />
          {!form.id && <Field label="שם משתמש (אנגלית)"><input dir="ltr" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></Field>}
          <Field label="שם תצוגה"><input value={form.display_name} onChange={e => setForm({ ...form, display_name: e.target.value })} /></Field>
          <Field label="תפקיד"><Select value={form.role} onChange={v => setForm({ ...form, role: v })} options={[{ key: 'editor', label: 'עורך — עריכת תוכן' }, { key: 'admin', label: 'מנהל — כולל הגדרות, משתמשים ומסכים' }]} /></Field>
          <Field label={form.id ? 'סיסמה חדשה (ריק = ללא שינוי)' : 'סיסמה ראשונית'} hint="לפחות 10 תווים, אותיות וספרות. המשתמש יתבקש להחליף."><input type="password" autoComplete="new-password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></Field>
          {form.id && <Toggle checked={form.is_active} onChange={v => setForm({ ...form, is_active: v })} label="פעיל" />}
        </Modal>
      )}
    </div>
  )
}

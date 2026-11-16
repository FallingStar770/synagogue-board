import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, download, get, post } from '../api'
import { Btn, Card, ErrorBox, Loading, PageHeader, fmtDateTime, useConfirm, useToast } from '../ui'

const ACTIONS: Record<string, string> = { create: 'יצירה', update: 'עדכון', delete: 'מחיקה', login: 'התחברות', logout: 'התנתקות', login_failed: 'ניסיון התחברות כושל', reorder: 'שינוי סדר', duplicate: 'שכפול', upload: 'העלאה', import: 'ייבוא', backup: 'גיבוי', restore: 'שחזור', rebuild: 'בנייה מחדש', revoke: 'ביטול', rotate_token: 'החלפת קוד', change_password: 'שינוי סיסמה', exception: 'חריג' }

export default function Maintenance() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const status = useQuery({ queryKey: ['status'], queryFn: () => get('/maintenance/status') })
  const [page, setPage] = useState(0)
  const logs = useQuery({ queryKey: ['audit', page], queryFn: () => get(`/audit-logs?limit=50&offset=${page * 50}`) })
  const [file, setFile] = useState<File | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const restore = async () => {
    if (!file || !(await confirm('השחזור יחליף את כל הנתונים הקיימים בנתוני הגיבוי ויתנתק מכל המשתמשים. להמשיך?'))) return
    try { const f = new FormData(); f.append('file', file); const r = await api('/maintenance/restore', { form: f }); toast(r.message); setTimeout(() => location.reload(), 1500) } catch (e) { setErr(e) }
  }
  const s = status.data
  return (
    <div>
      <PageHeader title="תחזוקה וגיבוי" subtitle="מצב המערכת, גיבוי ושחזור, ויומן פעולות" />
      {dialog}
      <div className="dash-grid">
        <Card title="מצב המערכת" actions={<Btn icon="refresh" onClick={() => status.refetch()}>רענון</Btn>}>
          {!s ? <Loading /> : <dl className="kv">
            <div><dt>שעת שרת</dt><dd>{fmtDateTime(s.server_time)}</dd></div>
            <div><dt>מנוע זמנים</dt><dd><small>{s.engine}</small></dd></div>
            <div><dt>מסד נתונים</dt><dd><small>{s.database?.split(' ').slice(0, 2).join(' ')}</small></dd></div>
            <div><dt>גרסת נתוני תצוגה</dt><dd>{s.snapshot ? `${s.snapshot.version} (${Math.round(s.snapshot.size / 1024)}KB)` : '—'}</dd></div>
            {Object.entries(s.counts).map(([k, v]) => <div key={k}><dt>{({ screens: 'מסכים', announcements: 'הודעות', prayers: 'תפילות', halachot: 'הלכות', memorials: 'עילוי נשמת', tzadikim: 'צדיקים', media: 'קבצי מדיה', users: 'משתמשים' } as any)[k]}</dt><dd>{String(v)}</dd></div>)}
          </dl>}
          <Btn icon="refresh" onClick={async () => { const r = await post('/maintenance/rebuild-snapshot'); toast(`נבנתה גרסת תצוגה ${r.version}`); qc.invalidateQueries({ queryKey: ['status'] }) }}>חישוב מחדש של נתוני התצוגה</Btn>
        </Card>
        <Card title="גיבוי ושחזור">
          <p className="muted">קובץ הגיבוי כולל את כל התוכן, ההגדרות, המשתמשים (סיסמאות מוצפנות בגיבוב) והתמונות. שמרו אותו במקום מאובטח. לגיבוי מוצפן ומתוזמן של מסד הנתונים ראו <code>scripts/backup.sh</code>.</p>
          <Btn kind="primary" icon="download" onClick={() => download('/maintenance/backup', `synagogue-backup-${new Date().toISOString().slice(0, 10)}.json`)}>הורדת גיבוי מלא</Btn>
          <fieldset><legend>שחזור מגיבוי</legend>
            <input type="file" accept="application/json,.json" aria-label="קובץ גיבוי" onChange={e => setFile(e.target.files?.[0] || null)} />
            <ErrorBox error={err} />
            <Btn kind="danger" icon="upload" disabled={!file} onClick={restore}>שחזור</Btn>
          </fieldset>
        </Card>
      </div>
      <Card title="יומן פעולות">
        {logs.isLoading ? <Loading /> : <>
          <div className="table-wrap"><table>
            <thead><tr><th>זמן</th><th>משתמש</th><th>פעולה</th><th>רכיב</th><th>פרטים</th><th>IP</th></tr></thead>
            <tbody>{logs.data?.items.map((l: any) => (
              <tr key={l.id}><td className="nowrap">{fmtDateTime(l.created_at)}</td><td>{l.username || '—'}</td><td>{ACTIONS[l.action] || l.action}</td><td>{l.entity}</td>
                <td><small className="muted">{l.details ? JSON.stringify(l.details).slice(0, 80) : ''}</small></td><td><small>{l.ip}</small></td></tr>))}</tbody>
          </table></div>
          <div className="pager"><Btn disabled={page === 0} onClick={() => setPage(page - 1)}>חדשים יותר</Btn><span>{logs.data?.total} רשומות</span><Btn disabled={(page + 1) * 50 >= (logs.data?.total || 0)} onClick={() => setPage(page + 1)}>ישנים יותר</Btn></div>
        </>}
      </Card>
    </div>
  )
}

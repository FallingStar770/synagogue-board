import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, get, post } from '../api'
import { Badge, Btn, Card, Empty, Field, Icon, Loading, Modal, PageHeader, fmtDateTime, useConfirm, useToast } from '../ui'

const STATUS: Record<string, [string, 'ok' | 'warn' | 'off' | 'neutral']> = { online: ['מחובר', 'ok'], stale: ['לא עדכני', 'warn'], offline: ['מנותק', 'off'], never: ['טרם התחבר', 'neutral'] }

export default function Devices() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const { data = [], isLoading } = useQuery<any[]>({ queryKey: ['devices'], queryFn: () => get('/devices'), refetchInterval: 20000 })
  const [name, setName] = useState('')
  const [token, setToken] = useState<{ name: string; token: string } | null>(null)
  const displayBase = new URL('../display/', window.location.href.split('#')[0]).href
  const pairUrl = token ? `${displayBase}#pair=${token.token}` : ''
  const create = async () => {
    try { const d = await post('/devices', { name }); setToken({ name: d.name, token: d.token }); setName(''); qc.invalidateQueries({ queryKey: ['devices'] }) } catch (e) { toast((e as Error).message, 'error') }
  }
  const rotate = async (d: any) => {
    if (!(await confirm(`ליצור קוד חדש ל"${d.name}"? הקוד הקודם יפסיק לעבוד מיד.`))) return
    const r = await post(`/devices/${d.id}/rotate`); setToken({ name: r.name, token: r.token }); qc.invalidateQueries({ queryKey: ['devices'] })
  }
  return (
    <div>
      <PageHeader title="מסכי טלוויזיה" subtitle="צימוד מסכים בהרשאת קריאה בלבד, מעקב חיבור, וביטול/החלפת קוד התקן" />
      {dialog}
      <Card title="צימוד מסך חדש">
        <div className="toolbar">
          <input aria-label="שם המסך" placeholder="לדוגמה: טלוויזיה בהיכל" value={name} onChange={e => setName(e.target.value)} />
          <Btn kind="primary" icon="plus" disabled={!name} onClick={create}>יצירת קוד התקן</Btn>
        </div>
        <ol className="steps">
          <li>חברו את ההתקן (Android TV Box / Mini PC) לטלוויזיה ב-HDMI ולרשת.</li>
          <li>פתחו בדפדפן ההתקן את כתובת הצימוד שתוצג כאן (פעם אחת בלבד). הקוד נשמר בהתקן — אין להזין סיסמת מנהל בטלוויזיה.</li>
          <li>הגדירו מצב קיוסק והפעלה אוטומטית — ראו <code>docs/KIOSK_SETUP.md</code>.</li>
        </ol>
      </Card>
      <Card title="מסכים מצומדים">
        {isLoading ? <Loading /> : !data.length ? <Empty>אין מסכים מצומדים</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th>שם</th><th>מצב</th><th>נראה לאחרונה</th><th>גרסת נתונים</th><th>מסך נוכחי</th><th>קוד</th><th></th></tr></thead>
            <tbody>{data.map(d => {
              const [label, tone] = d.revoked ? ['בוטל', 'off' as const] : STATUS[d.status]
              return (
                <tr key={d.id}>
                  <td><strong>{d.name}</strong></td><td><Badge tone={tone}>{label}</Badge></td>
                  <td>{fmtDateTime(d.last_seen_at)}{d.last_ip && <small className="muted"> · {d.last_ip}</small>}</td>
                  <td>{d.last_snapshot_version ?? '—'}{d.last_status?.online === false && <Badge tone="warn">פועל ללא רשת</Badge>}</td>
                  <td>{d.last_status?.current_screen || ''}</td>
                  <td><code>…{d.token_hint}</code></td>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" aria-label="קוד חדש" title="החלפת קוד" onClick={() => rotate(d)}><Icon name="refresh" size={18} /></button>
                    {!d.revoked && <button type="button" className="icon-btn" aria-label="ביטול" title="ביטול גישה" onClick={async () => { if (await confirm('לבטל את הגישה של מסך זה?')) { await post(`/devices/${d.id}/revoke`); qc.invalidateQueries({ queryKey: ['devices'] }) } }}><Icon name="x" size={18} /></button>}
                    <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm('למחוק את המסך?')) { await del(`/devices/${d.id}`); qc.invalidateQueries({ queryKey: ['devices'] }) } }}><Icon name="trash" size={18} /></button>
                  </td>
                </tr>)
            })}</tbody>
          </table></div>
        )}
      </Card>
      {token && (
        <Modal title={`קוד התקן עבור "${token.name}"`} onClose={() => setToken(null)} footer={<Btn kind="primary" onClick={() => setToken(null)}>סיימתי</Btn>}>
          <p><strong>הקוד מוצג פעם אחת בלבד.</strong> פתחו את הכתובת הבאה בדפדפן הטלוויזיה:</p>
          <Field label="כתובת צימוד"><input readOnly value={pairUrl} onFocus={e => e.target.select()} dir="ltr" /></Field>
          <Btn icon="copy" onClick={() => { navigator.clipboard?.writeText(pairUrl); toast('הועתק') }}>העתקה</Btn>
          <p className="muted">לאחר הצימוד הקוד נמחק מהכתובת ונשמר רק בהתקן. ניתן לבטל או להחליף אותו בכל עת.</p>
        </Modal>
      )}
    </div>
  )
}

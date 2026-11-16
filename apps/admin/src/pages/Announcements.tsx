import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { del, get, patch, post } from '../api'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Icon, ImagePicker, Loading, Modal, PageHeader, ScreenLinks, SearchBox, Select, Toggle, fmtDateTime, useConfirm, useScreens, useToast } from '../ui'

type Ann = { id?: string; title: string; body_html: string; image_asset_id: string | null; image_url?: string | null; start_at: string | null; end_at: string | null; priority: number; enabled: boolean; hide_on_shabbat: boolean; screen_ids: string[]; is_active_now?: boolean }

const toLocal = (iso: string | null) => { if (!iso) return ''; const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16) }
const fromLocal = (v: string) => (v ? new Date(v).toISOString() : null)

export function RichText({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (ref.current && ref.current.innerHTML !== value) ref.current.innerHTML = value }, [])
  const exec = (cmd: string, arg?: string) => { ref.current?.focus(); document.execCommand(cmd, false, arg); onChange(ref.current?.innerHTML || '') }
  const wrapClass = (cls: string) => {
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return
    const range = sel.getRangeAt(0)
    const span = document.createElement('span')
    span.className = cls
    span.appendChild(range.extractContents())
    range.insertNode(span)
    onChange(ref.current?.innerHTML || '')
  }
  return (
    <div className="rte">
      <div className="rte-bar" role="toolbar" aria-label="עיצוב טקסט">
        <button type="button" onClick={() => exec('bold')} aria-label="מודגש"><b>B</b></button>
        <button type="button" onClick={() => exec('underline')} aria-label="קו תחתון"><u>U</u></button>
        <button type="button" onClick={() => exec('insertUnorderedList')} aria-label="רשימה">• רשימה</button>
        <button type="button" onClick={() => wrapClass('c-gold')} aria-label="צבע זהב" className="sw gold">א</button>
        <button type="button" onClick={() => wrapClass('c-red')} aria-label="צבע אדום" className="sw red">א</button>
        <button type="button" onClick={() => wrapClass('c-blue')} aria-label="צבע כחול" className="sw blue">א</button>
        <button type="button" onClick={() => wrapClass('big')} aria-label="טקסט גדול">A+</button>
        <button type="button" onClick={() => exec('removeFormat')} aria-label="ניקוי עיצוב">נקה</button>
      </div>
      <div ref={ref} className="rte-area" contentEditable role="textbox" aria-multiline="true" aria-label="תוכן ההודעה"
        onInput={e => onChange((e.target as HTMLDivElement).innerHTML)} suppressContentEditableWarning />
      <small className="hint">התוכן מנוקה בשרת מקוד לא בטוח (HTML מסונן).</small>
    </div>
  )
}

function AnnForm({ initial, onClose }: { initial: Ann; onClose: () => void }) {
  const [a, setA] = useState<Ann>(initial)
  const qc = useQueryClient()
  const toast = useToast()
  const save = useMutation({
    mutationFn: () => {
      const body = { ...a }; delete body.id; delete body.image_url; delete body.is_active_now
      return a.id ? patch(`/announcements/${a.id}`, body) : post('/announcements', body)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['announcements'] }); toast('ההודעה נשמרה'); onClose() },
  })
  return (
    <Modal wide title={a.id ? 'עריכת הודעה' : 'הודעה חדשה'} onClose={onClose}
      footer={<><Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending || !a.title}>שמירה</Btn><Btn onClick={onClose}>ביטול</Btn></>}>
      <ErrorBox error={save.error} />
      <Field label="כותרת"><input value={a.title} maxLength={200} onChange={e => setA({ ...a, title: e.target.value })} required /></Field>
      <Field label="תוכן"><RichText value={a.body_html} onChange={v => setA({ ...a, body_html: v })} /></Field>
      <Field label="תמונה (אופציונלי)"><ImagePicker value={a.image_asset_id} url={a.image_url} onChange={(id, url) => setA({ ...a, image_asset_id: id, image_url: url })} /></Field>
      <div className="grid3">
        <Field label="מתאריך ושעה"><input type="datetime-local" value={toLocal(a.start_at)} onChange={e => setA({ ...a, start_at: fromLocal(e.target.value) })} /></Field>
        <Field label="עד תאריך ושעה" hint="לאחר מועד זה ההודעה תוסתר אוטומטית — גם ללא אינטרנט"><input type="datetime-local" value={toLocal(a.end_at)} onChange={e => setA({ ...a, end_at: fromLocal(e.target.value) })} /></Field>
        <Field label="עדיפות" hint="גבוהה מוצגת ראשונה"><Select value={String(a.priority)} onChange={v => setA({ ...a, priority: +v })} options={[{ key: '10', label: 'דחוף' }, { key: '5', label: 'גבוהה' }, { key: '0', label: 'רגילה' }, { key: '-5', label: 'נמוכה' }]} /></Field>
      </div>
      <div className="grid2">
        <Toggle checked={a.enabled} onChange={v => setA({ ...a, enabled: v })} label="הצג בלוח" />
        <Toggle checked={a.hide_on_shabbat} onChange={v => setA({ ...a, hide_on_shabbat: v })} label="הסתרה בשבת ובחג" />
      </div>
      <Field label="שיוך למסכים"><ScreenLinks types={['announcements', 'combined']} value={a.screen_ids} onChange={v => setA({ ...a, screen_ids: v })} /></Field>
    </Modal>
  )
}

export default function Announcements() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [q, setQ] = useState('')
  const [screen, setScreen] = useState('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [sel, setSel] = useState<string[]>([])
  const [editing, setEditing] = useState<Ann | null>(null)
  const { data: screens = [] } = useScreens()
  const params = new URLSearchParams({ limit: '200', ...(q && { q }), ...(screen && { screen_id: screen }), ...(activeOnly && { active_only: 'true' }) })
  const { data, isLoading, error } = useQuery({ queryKey: ['announcements', q, screen, activeOnly], queryFn: () => get('/announcements?' + params) })
  const items: Ann[] = data?.items || []
  const refresh = () => qc.invalidateQueries({ queryKey: ['announcements'] })
  const removeMany = async (ids: string[]) => {
    if (!(await confirm(ids.length > 1 ? `למחוק ${ids.length} הודעות?` : 'למחוק את ההודעה?'))) return
    try { for (const id of ids) await del(`/announcements/${id}`); setSel([]); refresh(); toast('נמחק') } catch (e) { toast((e as Error).message, 'error') }
  }
  const dup = async (id: string) => { try { await post(`/announcements/${id}/duplicate`); refresh(); toast('ההודעה שוכפלה (כבויה)') } catch (e) { toast((e as Error).message, 'error') } }
  return (
    <div>
      <PageHeader title="הודעות" subtitle="הודעות לציבור עם תוקף, עדיפות, תמונה ושיוך למסכים"
        actions={<Btn kind="primary" icon="plus" onClick={() => setEditing({ title: '', body_html: '', image_asset_id: null, start_at: null, end_at: null, priority: 0, enabled: true, hide_on_shabbat: false, screen_ids: [] })}>הודעה חדשה</Btn>} />
      {dialog}
      <Card>
        <div className="toolbar">
          <SearchBox value={q} onChange={setQ} placeholder="חיפוש לפי כותרת או תוכן" />
          <Select value={screen} onChange={setScreen} placeholder="כל המסכים" options={screens.filter(s => ['announcements', 'combined'].includes(s.type)).map(s => ({ key: s.id, label: s.name }))} />
          <Toggle checked={activeOnly} onChange={setActiveOnly} label="רק פעילות כעת" />
          {sel.length > 0 && <Btn kind="danger" icon="trash" onClick={() => removeMany(sel)}>מחיקת {sel.length} נבחרות</Btn>}
        </div>
        <ErrorBox error={error} />
        {isLoading ? <Loading /> : !items.length ? <Empty>אין הודעות להצגה</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr>
              <th><input type="checkbox" aria-label="בחירת הכל" checked={sel.length === items.length} onChange={e => setSel(e.target.checked ? items.map(i => i.id!) : [])} /></th>
              <th>כותרת</th><th>תוקף</th><th>עדיפות</th><th>מסכים</th><th>מצב</th><th></th>
            </tr></thead>
            <tbody>{items.map(a => (
              <tr key={a.id}>
                <td><input type="checkbox" aria-label={`בחירת ${a.title}`} checked={sel.includes(a.id!)} onChange={e => setSel(e.target.checked ? [...sel, a.id!] : sel.filter(x => x !== a.id))} /></td>
                <td><strong>{a.title}</strong>{a.image_url && <Icon name="image" size={16} />}{a.hide_on_shabbat && <Badge>מוסתר בשבת</Badge>}</td>
                <td className="nowrap">{a.start_at || a.end_at ? <>{fmtDateTime(a.start_at) || '—'} עד {fmtDateTime(a.end_at) || '—'}</> : 'ללא הגבלה'}</td>
                <td>{a.priority >= 10 ? 'דחוף' : a.priority > 0 ? 'גבוהה' : a.priority < 0 ? 'נמוכה' : 'רגילה'}</td>
                <td>{a.screen_ids.length ? a.screen_ids.map(id => screens.find(s => s.id === id)?.name).filter(Boolean).join(', ') : 'כל מסכי ההודעות'}</td>
                <td>{a.is_active_now ? <Badge tone="ok">מוצגת</Badge> : a.enabled ? <Badge tone="warn">מחוץ לתוקף</Badge> : <Badge tone="off">כבויה</Badge>}</td>
                <td className="row-actions">
                  <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditing(a)}><Icon name="edit" size={18} /></button>
                  <button type="button" className="icon-btn" aria-label="שכפול" onClick={() => dup(a.id!)}><Icon name="copy" size={18} /></button>
                  <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={() => removeMany([a.id!])}><Icon name="trash" size={18} /></button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      {editing && <AnnForm initial={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

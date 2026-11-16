import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { del, get, patch, post, put } from '../api'
import type { Screen } from '../types'
import { Badge, Btn, Card, CheckList, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, Select, Toggle, WeekdayPicker, useConfirm, useToast } from '../ui'
import { TvFrame } from './DisplayPreview'

const DAYS = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'שבת']

function ConfigEditor({ s, set, options, selections }: { s: Screen; set: (c: Record<string, any>) => void; options: any; selections: any[] }) {
  const c = s.config || {}
  const upd = (p: Record<string, any>) => set({ ...c, ...p })
  switch (s.type) {
    case 'clock':
      return <>
        <Toggle checked={c.show_seconds !== false} onChange={v => upd({ show_seconds: v })} label="הצגת שניות" />
        <Field label="זמנים מתחת לשעון"><CheckList columns={3} value={c.zmanim || []} onChange={v => upd({ zmanim: v })} options={options?.zmanim || []} /></Field>
      </>
    case 'announcements':
      return <Field label="מספר הודעות בעמוד"><Select value={String(c.per_page || 2)} onChange={v => upd({ per_page: +v })} options={[1, 2, 3].map(n => ({ key: String(n), label: String(n) }))} /></Field>
    case 'halacha':
      return <Field label="מקור ההלכות (בחירת הלכות)" hint="ניתן להגדיר בחירות בעמוד 'הלכות'">
        <Select value={c.selection_id || ''} onChange={v => upd({ selection_id: v || null })} placeholder="הבחירה הפעילה הראשונה" options={selections.map(x => ({ key: x.id, label: x.name }))} />
      </Field>
    case 'memorials':
      return <div className="grid2">
        <Field label="סגנון"><Select value={c.style || 'list'} onChange={v => upd({ style: v })} options={[{ key: 'list', label: 'רשימה' }, { key: 'cards', label: 'כרטיסים' }, { key: 'tree', label: 'לוח זיכרון (עץ)' }]} /></Field>
        <Field label="מה להציג"><Select value={c.mode || 'both'} onChange={v => upd({ mode: v })} options={[{ key: 'both', label: 'אזכרות השבוע + רשימה קבועה' }, { key: 'week', label: 'אזכרות השבוע בלבד' }, { key: 'permanent', label: 'רשימה קבועה בלבד' }]} /></Field>
      </div>
    case 'hilula':
      return <>
        <Field label="רוחב התמונה (%)" hint="ברירת מחדל 38% (תבנית עם תמונה בלבד)"><input type="number" min={25} max={50} value={c.image_percent ?? 38} onChange={e => upd({ image_percent: +e.target.value })} /></Field>
        <Toggle checked={c.show_upcoming !== false} onChange={v => upd({ show_upcoming: v })} label="הצגת 'ההילולות הקרובות' בצד" />
      </>
    case 'zmanim':
      return <>
        <Toggle checked={c.show_learning !== false} onChange={v => upd({ show_learning: v })} label="הצגת לימוד יומי" />
        <Toggle checked={c.show_additions !== false} onChange={v => upd({ show_additions: v })} label="הצגת הוספות בתפילה ותזכורות" />
      </>
    default:
      return <p className="muted">אין הגדרות נוספות לסוג מסך זה.</p>
  }
}

function ScreenForm({ initial, onClose, types }: { initial: Screen; onClose: () => void; types: any }) {
  const [s, setS] = useState<Screen>(initial)
  const qc = useQueryClient()
  const toast = useToast()
  const { data: options } = useQuery({ queryKey: ['options'], queryFn: () => get('/settings/options') })
  const { data: selections = [] } = useQuery<any[]>({ queryKey: ['selections'], queryFn: () => get('/halachot/selections') })
  const [preview, setPreview] = useState(false)
  const save = useMutation({
    mutationFn: () => {
      const body = { name: s.name, template_key: s.template_key, enabled: s.enabled, duration_seconds: s.duration_seconds, config: s.config,
        conditions: s.conditions, fallback: s.fallback, fallback_text: s.fallback_text }
      return s.id ? patch(`/screens/${s.id}`, body) : post('/screens', { ...body, type: s.type })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['screens'] }); toast('המסך נשמר'); onClose() },
  })
  const cond = s.conditions || { days_of_week: [], shabbat_mode: 'any' }
  const setCond = (p: Partial<Screen['conditions']>) => setS({ ...s, conditions: { ...cond, ...p } })
  const templates = (types?.templates || []).filter((t: any) => t.screen_type === s.type)
  return (
    <Modal wide title={s.id ? `עריכת מסך: ${initial.name}` : 'מסך חדש'} onClose={onClose}
      footer={<>
        <Btn kind="primary" icon="check" disabled={save.isPending} onClick={() => save.mutate()}>שמירה</Btn>
        {s.id && <Btn icon="eye" onClick={() => setPreview(!preview)}>{preview ? 'הסתרת תצוגה מקדימה' : 'תצוגה מקדימה'}</Btn>}
        <Btn onClick={onClose}>ביטול</Btn>
      </>}>
      <ErrorBox error={save.error} />
      {preview && s.id && <TvFrame title="תצוגה מקדימה" src={`../display/?preview=1&screen=${s.id}`} />}
      <div className="grid3">
        <Field label="שם המסך"><input value={s.name} onChange={e => setS({ ...s, name: e.target.value })} required /></Field>
        <Field label="סוג">
          <Select value={s.type} onChange={v => {
            const tpl = (types?.templates || []).find((t: any) => t.screen_type === v)
            setS({ ...s, type: v, template_key: tpl?.key || 'default', config: tpl?.default_config || {} })
          }} options={types?.types || []} />
        </Field>
        <Field label="משך הצגה (שניות)"><input type="number" min={3} max={3600} value={s.duration_seconds} onChange={e => setS({ ...s, duration_seconds: +e.target.value })} /></Field>
      </div>
      {s.id && <small className="hint">שינוי סוג מסך קיים אינו נתמך — צרו מסך חדש.</small>}
      <div className="grid2">
        <Field label="תבנית עיצוב"><Select value={s.template_key} onChange={v => {
          const t = templates.find((x: any) => x.key === v)
          setS({ ...s, template_key: v, config: { ...(t?.default_config || {}), ...s.config, ...(s.type === 'memorials' ? { style: t?.default_config?.style } : {}) } })
        }} options={templates.map((t: any) => ({ key: t.key, label: t.name }))} /></Field>
        <Field label="מצב"><Toggle checked={s.enabled} onChange={v => setS({ ...s, enabled: v })} label={s.enabled ? 'פעיל — מוצג בלוח' : 'כבוי'} /></Field>
      </div>
      <fieldset><legend>הגדרות תוכן</legend><ConfigEditor s={s} set={c => setS({ ...s, config: c })} options={options} selections={selections} /></fieldset>
      <fieldset>
        <legend>תנאי הצגה</legend>
        <Field label="ימים בשבוע" hint="ללא בחירה — בכל יום"><WeekdayPicker value={cond.days_of_week || []} onChange={v => setCond({ days_of_week: v })} /></Field>
        <div className="grid3">
          <Field label="שבת וחג"><Select value={cond.shabbat_mode || 'any'} onChange={v => setCond({ shabbat_mode: v as any })} options={[{ key: 'any', label: 'תמיד' }, { key: 'only', label: 'רק בשבת וחג' }, { key: 'hide', label: 'להסתיר בשבת וחג' }]} /></Field>
          <Field label="משעה"><input type="time" value={cond.time_from || ''} onChange={e => setCond({ time_from: e.target.value || null })} /></Field>
          <Field label="עד שעה"><input type="time" value={cond.time_to || ''} onChange={e => setCond({ time_to: e.target.value || null })} /></Field>
        </div>
        <div className="grid3">
          <Field label="מתאריך"><input type="date" value={cond.date_from || ''} onChange={e => setCond({ date_from: e.target.value || null })} /></Field>
          <Field label="עד תאריך"><input type="date" value={cond.date_to || ''} onChange={e => setCond({ date_to: e.target.value || null })} /></Field>
          <Field label="כשאין תוכן"><Select value={s.fallback} onChange={v => setS({ ...s, fallback: v as any })} options={[{ key: 'skip', label: 'דילוג על המסך' }, { key: 'message', label: 'הצגת הודעה חלופית' }]} /></Field>
        </div>
        {s.fallback === 'message' && <Field label="הודעה חלופית"><input value={s.fallback_text || ''} onChange={e => setS({ ...s, fallback_text: e.target.value })} /></Field>}
      </fieldset>
    </Modal>
  )
}

export default function Screens() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const { data, isLoading, error } = useQuery<Screen[]>({ queryKey: ['screens'], queryFn: () => get('/screens') })
  const { data: types } = useQuery({ queryKey: ['screen-types'], queryFn: () => get('/screens/types') })
  const [list, setList] = useState<Screen[]>([])
  const [dirty, setDirty] = useState(false)
  const [editing, setEditing] = useState<Screen | null>(null)
  const [dragId, setDragId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  useEffect(() => { if (data && !dirty) setList(data) }, [data, dirty])
  const typeLabel = (k: string) => types?.types?.find((t: any) => t.key === k)?.label || k
  const move = (i: number, d: number) => {
    const j = i + d
    if (j < 0 || j >= list.length) return
    const next = [...list];[next[i], next[j]] = [next[j], next[i]]
    setList(next); setDirty(true)
  }
  const saveOrder = useMutation({
    mutationFn: () => put('/screens/order', { ids: list.map(s => s.id) }),
    onSuccess: () => { setDirty(false); qc.invalidateQueries({ queryKey: ['screens'] }); toast('סדר המסכים נשמר') },
    onError: (e: Error) => toast(e.message, 'error'),
  })
  const quick = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => patch(`/screens/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screens'] }),
    onError: (e: Error) => toast(e.message, 'error'),
  })
  const remove = async (s: Screen) => {
    if (!(await confirm(`למחוק את המסך "${s.name}"?`))) return
    try { await del(`/screens/${s.id}`); qc.invalidateQueries({ queryKey: ['screens'] }); toast('המסך נמחק') } catch (e) { toast((e as Error).message, 'error') }
  }
  const total = list.filter(s => s.enabled).reduce((a, s) => a + s.duration_seconds, 0)
  const shown = list.filter(s => !filter || s.name.includes(filter) || typeLabel(s.type).includes(filter))
  return (
    <div>
      <PageHeader title="מסכים" subtitle={`בחרו אילו מסכים יוצגו, באיזה סדר ולכמה זמן. סבב מלא: ${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')} דקות`}
        actions={<>
          {dirty && <Btn kind="primary" icon="check" onClick={() => saveOrder.mutate()} disabled={saveOrder.isPending}>שמירת סדר</Btn>}
          <Btn kind="primary" icon="plus" onClick={() => setEditing({ id: '', name: '', type: 'announcements', template_key: 'default', enabled: true, sort_order: 0, duration_seconds: 20, config: { per_page: 2 }, conditions: { days_of_week: [], shabbat_mode: 'any' }, fallback: 'skip', fallback_text: null })}>מסך חדש</Btn>
        </>} />
      {dialog}
      <ErrorBox error={error} />
      <Card>
        <div className="toolbar"><input type="search" placeholder="סינון לפי שם או סוג" aria-label="סינון" value={filter} onChange={e => setFilter(e.target.value)} />
          <small className="muted">גררו שורה או השתמשו בחצים לשינוי הסדר</small></div>
        {isLoading ? <Loading /> : !list.length ? <Empty>אין מסכים</Empty> : (
          <ul className="screen-list" aria-label="רשימת מסכים לפי סדר הצגה">
            {shown.map((s) => {
              const i = list.indexOf(s)
              const c = s.conditions || ({} as any)
              return (
                <li key={s.id} draggable={!filter} className={(dragId === s.id ? 'dragging ' : '') + (s.enabled ? '' : 'disabled')}
                  onDragStart={() => setDragId(s.id)} onDragEnd={() => setDragId(null)}
                  onDragOver={e => {
                    e.preventDefault()
                    if (!dragId || dragId === s.id) return
                    const from = list.findIndex(x => x.id === dragId)
                    const next = [...list]; const [m] = next.splice(from, 1); next.splice(i, 0, m)
                    setList(next); setDirty(true)
                  }}>
                  <span className="grip" aria-hidden="true"><Icon name="grip" /></span>
                  <span className="order">{i + 1}</span>
                  <div className="info">
                    <strong>{s.name}</strong>
                    <span className="muted">{typeLabel(s.type)}
                      {c.days_of_week?.length ? ' · ' + c.days_of_week.map((d: number) => DAYS[d]).join(' ') : ''}
                      {c.shabbat_mode === 'only' ? ' · רק בשבת/חג' : c.shabbat_mode === 'hide' ? ' · לא בשבת/חג' : ''}
                      {c.time_from || c.time_to ? ` · ${c.time_from || '00:00'}–${c.time_to || '24:00'}` : ''}
                    </span>
                  </div>
                  <label className="dur"><input type="number" min={3} max={3600} aria-label={`משך הצגה של ${s.name}`} defaultValue={s.duration_seconds} key={s.duration_seconds}
                    onBlur={e => { const v = +e.target.value; if (v >= 3 && v !== s.duration_seconds) quick.mutate({ id: s.id, body: { duration_seconds: v } }) }} />שנ׳</label>
                  <Toggle checked={s.enabled} onChange={v => quick.mutate({ id: s.id, body: { enabled: v } })} label={s.enabled ? 'פעיל' : 'כבוי'} />
                  <div className="row-actions">
                    <button type="button" className="icon-btn" aria-label="הזזה למעלה" onClick={() => move(i, -1)}><Icon name="up" size={18} /></button>
                    <button type="button" className="icon-btn" aria-label="הזזה למטה" onClick={() => move(i, 1)}><Icon name="down" size={18} /></button>
                    <button type="button" className="icon-btn" aria-label={`עריכת ${s.name}`} onClick={() => setEditing(s)}><Icon name="edit" size={18} /></button>
                    <a className="icon-btn" aria-label={`תצוגה מקדימה של ${s.name}`} href={`../display/?preview=1&screen=${s.id}`} target="_blank" rel="noopener"><Icon name="eye" size={18} /></a>
                    <button type="button" className="icon-btn danger" aria-label={`מחיקת ${s.name}`} onClick={() => remove(s)}><Icon name="trash" size={18} /></button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        {dirty && <p className="banner warn">הסדר שונה ועדיין לא נשמר. <Btn kind="primary" onClick={() => saveOrder.mutate()}>שמירת סדר</Btn> <Btn kind="ghost" onClick={() => { setDirty(false); setList(data || []) }}>ביטול</Btn></p>}
      </Card>
      <Card title="מקרא"><p className="muted"><Badge tone="ok">פעיל</Badge> מוצג בסבב לפי הסדר והמשך. מסך ללא תוכן (למשל הילולה ביום ללא הילולה) ידולג אוטומטית או יציג הודעה חלופית לפי הגדרתו.</p></Card>
      {editing && <ScreenForm initial={editing} types={types} onClose={() => setEditing(null)} />}
    </div>
  )
}

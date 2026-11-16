import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, download, get, patch, post } from '../api'
import { emptyRule, type Rule } from '../types'
import { Badge, Btn, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, RuleEditor, ScreenLinks, SearchBox, Select, Toggle, useConfirm, useScreens, useToast } from '../ui'

type Prayer = Rule & { id?: string; prayer_type_id: string; name: string; description: string | null; location: string | null; enabled: boolean; sort_order: number; screen_ids: string[]; exceptions?: any[]; type_name?: string; day_kind_label?: string; time_label?: string }

export function ExceptionsEditor({ items, onAdd, onDelete }: { items: any[]; onAdd: (b: any) => Promise<void>; onDelete: (id: string) => Promise<void> }) {
  const [d, setD] = useState({ date: '', action: 'cancel', override_time: '', note: '' })
  return (
    <fieldset>
      <legend>חריגים בתאריכים מסוימים</legend>
      {items.length ? <ul className="mini-list">{items.map(e => (
        <li key={e.id}>{new Date(e.date).toLocaleDateString('he-IL')} — {e.action === 'cancel' ? 'מבוטל' : `בשעה ${e.override_time}`}{e.note && ` (${e.note})`}
          <button type="button" className="icon-btn danger" aria-label="מחיקת חריג" onClick={() => onDelete(e.id)}><Icon name="trash" size={16} /></button></li>
      ))}</ul> : <p className="muted">אין חריגים</p>}
      <div className="grid4">
        <Field label="תאריך"><input type="date" value={d.date} onChange={e => setD({ ...d, date: e.target.value })} /></Field>
        <Field label="פעולה"><Select value={d.action} onChange={v => setD({ ...d, action: v })} options={[{ key: 'cancel', label: 'ביטול' }, { key: 'override', label: 'שעה אחרת' }]} /></Field>
        {d.action === 'override' && <Field label="שעה"><input type="time" value={d.override_time} onChange={e => setD({ ...d, override_time: e.target.value })} /></Field>}
        <Field label="הערה"><input value={d.note} onChange={e => setD({ ...d, note: e.target.value })} /></Field>
      </div>
      <Btn icon="plus" disabled={!d.date} onClick={async () => { await onAdd({ ...d, override_time: d.override_time || null, note: d.note || null }); setD({ date: '', action: 'cancel', override_time: '', note: '' }) }}>הוספת חריג</Btn>
    </fieldset>
  )
}

function PrayerForm({ initial, onClose, types, options }: { initial: Prayer; onClose: () => void; types: any[]; options: any }) {
  const [p, setP] = useState<Prayer>(initial)
  const qc = useQueryClient()
  const toast = useToast()
  const save = useMutation({
    mutationFn: () => {
      const body: any = { ...p }
      for (const k of ['id', 'exceptions', 'type_name', 'type_key', 'day_kind_label', 'time_label', 'created_at', 'updated_at']) delete body[k]
      return p.id ? patch(`/prayers/${p.id}`, body) : post('/prayers', body)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['prayers'] }); toast('נשמר'); onClose() },
  })
  const exc = useQuery({ queryKey: ['prayers'], queryFn: () => get('/prayers'), enabled: !!p.id, select: (all: any[]) => all.find(x => x.id === p.id)?.exceptions || [] })
  return (
    <Modal wide title={p.id ? `עריכת ${initial.name}` : 'תפילה / מניין חדש'} onClose={onClose}
      footer={<><Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending || !p.name || !p.prayer_type_id}>שמירה</Btn><Btn onClick={onClose}>ביטול</Btn></>}>
      <ErrorBox error={save.error} />
      <div className="grid3">
        <Field label="סוג תפילה"><Select value={p.prayer_type_id} onChange={v => setP({ ...p, prayer_type_id: v })} options={types.map(t => ({ key: t.id, label: t.name }))} placeholder="בחירה…" /></Field>
        <Field label="שם המניין" hint="לדוגמה: שחרית מניין א׳"><input value={p.name} onChange={e => setP({ ...p, name: e.target.value })} /></Field>
        <Field label="מיקום"><input value={p.location || ''} onChange={e => setP({ ...p, location: e.target.value || null })} placeholder="היכל / בית מדרש" /></Field>
      </div>
      <Field label="תיאור נוסף לתפילה"><input value={p.description || ''} onChange={e => setP({ ...p, description: e.target.value || null })} /></Field>
      <fieldset><legend>מתי</legend><RuleEditor rule={p} onChange={r => setP({ ...p, ...r })} options={options} /></fieldset>
      <div className="grid2">
        <Toggle checked={p.enabled} onChange={v => setP({ ...p, enabled: v })} label="הצג בלוח" />
        <Field label="סדר בתוך הסוג"><input type="number" value={p.sort_order} onChange={e => setP({ ...p, sort_order: +e.target.value })} /></Field>
      </div>
      <Field label="שיוך למסך"><ScreenLinks types={['prayers', 'prayers_lessons', 'combined', 'shabbat']} value={p.screen_ids} onChange={v => setP({ ...p, screen_ids: v })} /></Field>
      {p.id && <ExceptionsEditor items={exc.data || []}
        onAdd={async b => { try { await post(`/prayers/${p.id}/exceptions`, b); qc.invalidateQueries({ queryKey: ['prayers'] }); toast('החריג נוסף') } catch (e) { toast((e as Error).message, 'error') } }}
        onDelete={async id => { await del(`/prayers/exceptions/${id}`); qc.invalidateQueries({ queryKey: ['prayers'] }) }} />}
    </Modal>
  )
}

export function DayPreview({ path, render }: { path: string; render: (items: any[]) => React.ReactNode }) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10))
  const { data, isLoading, error } = useQuery({ queryKey: [path, date], queryFn: () => get(`${path}?date=${date}`) })
  return (
    <Card title="בדיקת זמנים לתאריך" actions={<input type="date" aria-label="תאריך לבדיקה" value={date} onChange={e => setDate(e.target.value)} />}>
      <ErrorBox error={error} />
      {isLoading ? <Loading /> : <>
        {data?.hebrew && <p className="muted">{data.hebrew}{data.holiday && ' · ' + data.holiday}</p>}
        {data?.items?.length ? render(data.items) : <p className="muted">אין פריטים בתאריך זה</p>}
      </>}
    </Card>
  )
}

export default function Prayers() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [q, setQ] = useState('')
  const [typeF, setTypeF] = useState('')
  const [screenF, setScreenF] = useState('')
  const [editing, setEditing] = useState<Prayer | null>(null)
  const { data: types = [] } = useQuery<any[]>({ queryKey: ['prayer-types'], queryFn: () => get('/prayer-types') })
  const { data: options } = useQuery({ queryKey: ['schedule-options'], queryFn: () => get('/schedule-options') })
  const { data: screens = [] } = useScreens()
  const params = new URLSearchParams({ ...(q && { q }), ...(typeF && { prayer_type_id: typeF }), ...(screenF && { screen_id: screenF }) })
  const { data = [], isLoading, error } = useQuery<Prayer[]>({ queryKey: ['prayers', q, typeF, screenF], queryFn: () => get('/prayers?' + params) })
  const remove = async (p: Prayer) => {
    if (!(await confirm(`למחוק את "${p.name}"?`))) return
    await del(`/prayers/${p.id}`); qc.invalidateQueries({ queryKey: ['prayers'] }); toast('נמחק')
  }
  const dup = async (p: Prayer) => { await post(`/prayers/${p.id}/duplicate`); qc.invalidateQueries({ queryKey: ['prayers'] }); toast('שוכפל') }
  const toggle = async (p: Prayer) => {
    const body: any = { ...p, enabled: !p.enabled }
    for (const k of ['id', 'exceptions', 'type_name', 'type_key', 'day_kind_label', 'time_label', 'created_at', 'updated_at']) delete body[k]
    await patch(`/prayers/${p.id}`, body); qc.invalidateQueries({ queryKey: ['prayers'] })
  }
  return (
    <div>
      <PageHeader title="זמני תפילות" subtitle="מניינים בשעה קבועה או יחסית לזריחה / שקיעה / צאת הכוכבים, ימים מיוחדים וחריגים"
        actions={<>
          <Btn icon="download" onClick={() => download('/prayers/export.csv', 'prayers.csv')}>ייצוא לאקסל</Btn>
          <Btn kind="primary" icon="plus" onClick={() => setEditing({ ...emptyRule(), day_kind: 'weekday', prayer_type_id: types[1]?.id || '', name: '', description: null, location: null, enabled: true, sort_order: 0, screen_ids: [] })}>תפילה חדשה</Btn>
        </>} />
      {dialog}
      <div className="two-col">
        <Card>
          <div className="toolbar">
            <SearchBox value={q} onChange={setQ} placeholder="חיפוש לפי שם" />
            <Select value={typeF} onChange={setTypeF} placeholder="כל סוגי התפילה" options={types.map(t => ({ key: t.id, label: t.name }))} />
            <Select value={screenF} onChange={setScreenF} placeholder="כל המסכים" options={screens.filter(s => ['prayers', 'prayers_lessons', 'combined', 'shabbat'].includes(s.type)).map(s => ({ key: s.id, label: s.name }))} />
          </div>
          <ErrorBox error={error} />
          {isLoading ? <Loading /> : !data.length ? <Empty>אין תפילות. לחצו "תפילה חדשה".</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>סוג</th><th>שם</th><th>ימים</th><th>שעה</th><th>חריגים</th><th>מצב</th><th></th></tr></thead>
              <tbody>{data.map(p => (
                <tr key={p.id} className={p.enabled ? '' : 'disabled'}>
                  <td>{p.type_name}</td><td><strong>{p.name}</strong>{p.location && <small className="muted"> · {p.location}</small>}</td>
                  <td>{p.day_kind_label}{p.day_kind === 'custom' && ` (${p.days_of_week.map(d => 'אבגדהוש'[d]).join(',')})`}{p.replaces_regular && <Badge tone="gold">מחליף</Badge>}</td>
                  <td className="nowrap">{p.time_label}</td>
                  <td>{p.exceptions?.length || ''}</td>
                  <td><Toggle checked={p.enabled} onChange={() => toggle(p)} /></td>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditing(p)}><Icon name="edit" size={18} /></button>
                    <button type="button" className="icon-btn" aria-label="שכפול" onClick={() => dup(p)}><Icon name="copy" size={18} /></button>
                    <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={() => remove(p)}><Icon name="trash" size={18} /></button>
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <DayPreview path="/prayers/day" render={items => <dl className="kv">{items.map((i: any) => <div key={i.id}><dt>{i.name}{i.note && <small className="muted"> ({i.note})</small>}</dt><dd>{i.time}</dd></div>)}</dl>} />
      </div>
      {editing && <PrayerForm initial={editing} types={types} options={options} onClose={() => setEditing(null)} />}
    </div>
  )
}

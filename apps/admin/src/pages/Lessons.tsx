import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, download, get, patch, post } from '../api'
import { emptyRule, type Rule } from '../types'
import { Btn, Card, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, RuleEditor, ScreenLinks, SearchBox, Toggle, useConfirm, useToast } from '../ui'
import { DayPreview, ExceptionsEditor } from './Prayers'

type Sched = Rule & { id?: string; exceptions?: any[]; time_label?: string; day_kind_label?: string }
type Lesson = { id?: string; title: string; teacher: string | null; location: string | null; description: string | null; enabled: boolean; sort_order: number; schedules: Sched[]; screen_ids: string[] }

function LessonForm({ initial, onClose, options }: { initial: Lesson; onClose: () => void; options: any }) {
  const [l, setL] = useState<Lesson>(initial)
  const qc = useQueryClient()
  const toast = useToast()
  const clean = (s: Sched) => { const x: any = { ...s }; for (const k of ['exceptions', 'time_label', 'day_kind_label', 'lesson_id']) delete x[k]; return x }
  const save = useMutation({
    mutationFn: () => {
      const body = { title: l.title, teacher: l.teacher, location: l.location, description: l.description, enabled: l.enabled, sort_order: l.sort_order, schedules: l.schedules.map(clean), screen_ids: l.screen_ids }
      return l.id ? patch(`/lessons/${l.id}`, body) : post('/lessons', body)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['lessons'] }); toast('השיעור נשמר'); onClose() },
  })
  const setSched = (i: number, r: Rule) => setL({ ...l, schedules: l.schedules.map((s, j) => (j === i ? { ...s, ...r } : s)) })
  return (
    <Modal wide title={l.id ? `עריכת שיעור: ${initial.title}` : 'שיעור חדש'} onClose={onClose}
      footer={<><Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending || !l.title}>שמירה</Btn><Btn onClick={onClose}>ביטול</Btn></>}>
      <ErrorBox error={save.error} />
      <div className="grid3">
        <Field label="שם השיעור"><input value={l.title} onChange={e => setL({ ...l, title: e.target.value })} /></Field>
        <Field label="שם המגיד שיעור"><input value={l.teacher || ''} onChange={e => setL({ ...l, teacher: e.target.value || null })} /></Field>
        <Field label="מיקום"><input value={l.location || ''} onChange={e => setL({ ...l, location: e.target.value || null })} /></Field>
      </div>
      <Field label="תיאור"><textarea rows={2} value={l.description || ''} onChange={e => setL({ ...l, description: e.target.value || null })} /></Field>
      {l.schedules.map((s, i) => (
        <fieldset key={s.id || i}>
          <legend>מועד {i + 1} {l.schedules.length > 1 && <button type="button" className="icon-btn danger" aria-label="הסרת מועד" onClick={() => setL({ ...l, schedules: l.schedules.filter((_, j) => j !== i) })}><Icon name="trash" size={16} /></button>}</legend>
          <RuleEditor rule={s} onChange={r => setSched(i, r)} options={options} />
          {s.id && <ExceptionsEditor items={s.exceptions || []}
            onAdd={async b => { try { await post(`/lessons/schedules/${s.id}/exceptions`, b); const all = await get('/lessons'); const fresh = all.find((x: any) => x.id === l.id); if (fresh) setL({ ...l, schedules: fresh.schedules }); qc.invalidateQueries({ queryKey: ['lessons'] }); toast('החריג נוסף') } catch (e) { toast((e as Error).message, 'error') } }}
            onDelete={async id => { await del(`/lessons/exceptions/${id}`); setL({ ...l, schedules: l.schedules.map(x => ({ ...x, exceptions: (x.exceptions || []).filter((e: any) => e.id !== id) })) }); qc.invalidateQueries({ queryKey: ['lessons'] }) }} />}
        </fieldset>
      ))}
      <Btn icon="plus" onClick={() => setL({ ...l, schedules: [...l.schedules, { ...emptyRule(), day_kind: 'sun_thu', fixed_time: '20:00' }] })}>הוספת מועד</Btn>
      <Toggle checked={l.enabled} onChange={v => setL({ ...l, enabled: v })} label="הצג בלוח" />
      <Field label="שיוך למסך"><ScreenLinks types={['lessons', 'prayers_lessons', 'combined']} value={l.screen_ids} onChange={v => setL({ ...l, screen_ids: v })} /></Field>
    </Modal>
  )
}

export default function Lessons() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<Lesson | null>(null)
  const { data: options } = useQuery({ queryKey: ['schedule-options'], queryFn: () => get('/schedule-options') })
  const { data = [], isLoading, error } = useQuery<Lesson[]>({ queryKey: ['lessons', q], queryFn: () => get('/lessons' + (q ? '?q=' + encodeURIComponent(q) : '')) })
  const remove = async (l: Lesson) => {
    if (!(await confirm(`למחוק את השיעור "${l.title}"?`))) return
    await del(`/lessons/${l.id}`); qc.invalidateQueries({ queryKey: ['lessons'] }); toast('נמחק')
  }
  return (
    <div>
      <PageHeader title="שיעורים" subtitle="שיעורים קבועים, מגידי שיעור ומועדים — בשעה קבועה או יחסית"
        actions={<>
          <Btn icon="download" onClick={() => download('/lessons/export.csv', 'lessons.csv')}>ייצוא לאקסל</Btn>
          <Btn kind="primary" icon="plus" onClick={() => setEditing({ title: '', teacher: null, location: null, description: null, enabled: true, sort_order: 0, schedules: [{ ...emptyRule(), day_kind: 'sun_thu', fixed_time: '20:00' }], screen_ids: [] })}>שיעור חדש</Btn>
        </>} />
      {dialog}
      <div className="two-col">
        <Card>
          <div className="toolbar"><SearchBox value={q} onChange={setQ} placeholder="חיפוש לפי שיעור או מגיד שיעור" /></div>
          <ErrorBox error={error} />
          {isLoading ? <Loading /> : !data.length ? <Empty>אין שיעורים</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>שיעור</th><th>מגיד שיעור</th><th>מועדים</th><th>מצב</th><th></th></tr></thead>
              <tbody>{data.map(l => (
                <tr key={l.id} className={l.enabled ? '' : 'disabled'}>
                  <td><strong>{l.title}</strong>{l.location && <small className="muted"> · {l.location}</small>}</td>
                  <td>{l.teacher}</td>
                  <td>{l.schedules.map((s, i) => <div key={i}>{s.day_kind_label} · {s.time_label}</div>)}</td>
                  <td>{l.enabled ? 'פעיל' : 'כבוי'}</td>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditing(l)}><Icon name="edit" size={18} /></button>
                    <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={() => remove(l)}><Icon name="trash" size={18} /></button>
                  </td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Card>
        <DayPreview path="/lessons/day" render={items => <dl className="kv">{items.map((i: any, k: number) => <div key={k}><dt>{i.title}{i.teacher && <small className="muted"> · {i.teacher}</small>}</dt><dd>{i.time}</dd></div>)}</dl>} />
      </div>
      {editing && <LessonForm initial={editing} options={options} onClose={() => setEditing(null)} />}
    </div>
  )
}

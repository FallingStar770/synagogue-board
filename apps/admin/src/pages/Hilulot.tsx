import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, get, patch, post } from '../api'
import { Badge, Btn, Card, Empty, ErrorBox, Field, HebrewDateInput, Icon, ImagePicker, Loading, Modal, PageHeader, SearchBox, Toggle, fmtDate, useConfirm, useToast } from '../ui'
import { TvFrame } from './DisplayPreview'

type HDate = { id?: string; hebrew_month: number; hebrew_day: number; leap_year_policy: string; display_start_offset_days: number; display_end_offset_days: number; enabled: boolean; hebrew_date_str?: string; next_date?: string }
type Tz = { id?: string; display_name: string; honorific: string | null; biography: string; teaching_title: string | null; teaching_text: string; teaching_source: string | null; image_asset_id: string | null; image_url?: string | null; image_alt: string | null; image_attribution: string | null; burial_place: string | null; death_hebrew_year: number | null; is_active: boolean; sort_order: number; dates: HDate[] }

const blank = (): Tz => ({ display_name: '', honorific: 'רבי', biography: '', teaching_title: 'מתורתו', teaching_text: '', teaching_source: null, image_asset_id: null, image_alt: null, image_attribution: null, burial_place: null, death_hebrew_year: null, is_active: true, sort_order: 0, dates: [{ hebrew_month: 7, hebrew_day: 1, leap_year_policy: 'adar_ii', display_start_offset_days: 0, display_end_offset_days: 0, enabled: true }] })

function TzForm({ initial, onClose }: { initial: Tz; onClose: () => void }) {
  const [t, setT] = useState<Tz>(initial)
  const [preview, setPreview] = useState<'' | 'auto' | 'image' | 'noimage'>('')
  const qc = useQueryClient()
  const toast = useToast()
  const errors: string[] = []
  if (!t.display_name.trim()) errors.push('שם הצדיק חובה')
  if (!t.biography.trim()) errors.push('תיאור חייו חובה')
  if (!t.teaching_text.trim()) errors.push('קטע לימוד חובה')
  if (t.biography.length > 6000) errors.push('תיאור ארוך מדי (עד 6000 תווים)')
  const save = useMutation({
    mutationFn: () => {
      const b: any = { ...t }
      delete b.id; delete b.image_url; delete b.created_at; delete b.updated_at
      b.dates = t.dates.map(({ hebrew_date_str: _a, next_date: _b, ...d }: any) => { delete d.tzadik_id; return d })
      return t.id ? patch(`/hilulot/${t.id}`, b) : post('/hilulot', b)
    },
    onSuccess: (r: any) => { qc.invalidateQueries({ queryKey: ['hilulot'] }); toast('נשמר'); setT({ ...t, id: r.id, dates: r.dates }) },
  })
  const setDate = (i: number, p: Partial<HDate>) => setT({ ...t, dates: t.dates.map((d, j) => (j === i ? { ...d, ...p } : d)) })
  return (
    <Modal wide title={t.id ? `עריכת ${initial.display_name}` : 'צדיק / יום הילולה חדש'} onClose={onClose}
      footer={<>
        <Btn kind="primary" icon="check" disabled={!!errors.length || save.isPending} onClick={() => save.mutate()}>שמירה</Btn>
        <Btn icon="eye" disabled={!t.id} title={t.id ? '' : 'יש לשמור לפני תצוגה מקדימה'} onClick={() => setPreview(preview ? '' : 'auto')}>תצוגה מקדימה</Btn>
        <Btn onClick={onClose}>סגירה</Btn>
      </>}>
      <ErrorBox error={save.error} />
      {errors.length > 0 && <small className="err">{errors.join(' · ')}</small>}
      {preview && t.id && <>
        <div className="tabs small" role="tablist">
          {(['auto', 'image', 'noimage'] as const).map(k => <button key={k} role="tab" aria-selected={preview === k} className={preview === k ? 'on' : ''} onClick={() => setPreview(k)}>{{ auto: 'אוטומטי', image: 'תבנית עם תמונה', noimage: 'תבנית ללא תמונה' }[k]}</button>)}
        </div>
        <TvFrame title="תצוגה מקדימה של יום ההילולה" src={`../display/?preview=1&hilula=${t.id}&layout=${preview}&v=${Date.now()}`} />
        <small className="hint">התצוגה מציגה את הנתונים השמורים. התבנית האוטומטית בוחרת "עם תמונה" רק כשהתמונה נטענת בהצלחה.</small>
      </>}
      <div className="grid3">
        <Field label="תואר"><input value={t.honorific || ''} onChange={e => setT({ ...t, honorific: e.target.value || null })} placeholder="רבי / הרב" /></Field>
        <Field label="שם הצדיק"><input value={t.display_name} onChange={e => setT({ ...t, display_name: e.target.value })} required /></Field>
        <Field label="מקום קבורה"><input value={t.burial_place || ''} onChange={e => setT({ ...t, burial_place: e.target.value || null })} /></Field>
      </div>
      <Field label="תולדות חייו" hint={`${t.biography.length}/6000 · טקסט ארוך יוקטן או יחולק לעמודים בתצוגה — לא ייחתך`}><textarea rows={5} value={t.biography} onChange={e => setT({ ...t, biography: e.target.value })} /></Field>
      <div className="grid2">
        <Field label="כותרת קטע הלימוד"><input value={t.teaching_title || ''} onChange={e => setT({ ...t, teaching_title: e.target.value || null })} /></Field>
        <Field label="מקור קטע הלימוד (ייחוס)"><input value={t.teaching_source || ''} onChange={e => setT({ ...t, teaching_source: e.target.value || null })} /></Field>
      </div>
      <Field label="קטע לימוד מתורתו"><textarea rows={4} value={t.teaching_text} onChange={e => setT({ ...t, teaching_text: e.target.value })} /></Field>
      <fieldset><legend>תמונה (אופציונלי)</legend>
        <ImagePicker value={t.image_asset_id} url={t.image_url} onChange={(id, url) => setT({ ...t, image_asset_id: id, image_url: url })} />
        <div className="grid2">
          <Field label="תיאור התמונה (נגישות)"><input value={t.image_alt || ''} onChange={e => setT({ ...t, image_alt: e.target.value || null })} /></Field>
          <Field label="ייחוס / זכויות התמונה"><input value={t.image_attribution || ''} onChange={e => setT({ ...t, image_attribution: e.target.value || null })} /></Field>
        </div>
        <small className="hint">עם תמונה: התמונה מימין והטקסט משמאל. ללא תמונה (או אם אינה נטענת): כותרת ממורכזת למעלה וטקסט על כל הרוחב.</small>
      </fieldset>
      {t.dates.map((d, i) => (
        <fieldset key={d.id || i}>
          <legend>תאריך ההילולה {t.dates.length > 1 && <button type="button" className="icon-btn danger" aria-label="הסרת תאריך" onClick={() => setT({ ...t, dates: t.dates.filter((_, j) => j !== i) })}><Icon name="trash" size={16} /></button>}</legend>
          <HebrewDateInput month={d.hebrew_month} day={d.hebrew_day} onChange={(m, dd) => setDate(i, { hebrew_month: m, hebrew_day: dd })} leapPolicy={d.leap_year_policy} onLeapPolicy={v => setDate(i, { leap_year_policy: v })} />
          <div className="grid3">
            <Field label="להציג ימים לפני"><input type="number" min={0} max={30} value={d.display_start_offset_days} onChange={e => setDate(i, { display_start_offset_days: +e.target.value })} /></Field>
            <Field label="להציג ימים אחרי"><input type="number" min={0} max={30} value={d.display_end_offset_days} onChange={e => setDate(i, { display_end_offset_days: +e.target.value })} /></Field>
            <Field label="פעיל"><Toggle checked={d.enabled} onChange={v => setDate(i, { enabled: v })} /></Field>
          </div>
          {d.next_date && <small className="hint">ההילולה הבאה: {fmtDate(d.next_date)}</small>}
        </fieldset>
      ))}
      <div className="grid3">
        <Field label="שנת פטירה עברית (מספר)" hint="לדוגמה 5330 עבור ש״ל"><input type="number" value={t.death_hebrew_year ?? ''} onChange={e => setT({ ...t, death_hebrew_year: e.target.value ? +e.target.value : null })} /></Field>
        <Field label="סדר (כשיש כמה צדיקים באותו יום)"><input type="number" value={t.sort_order} onChange={e => setT({ ...t, sort_order: +e.target.value })} /></Field>
        <Field label="מצב"><Toggle checked={t.is_active} onChange={v => setT({ ...t, is_active: v })} label={t.is_active ? 'פעיל' : 'כבוי'} /></Field>
      </div>
    </Modal>
  )
}

export default function Hilulot() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<Tz | null>(null)
  const { data = [], isLoading, error } = useQuery<Tz[]>({ queryKey: ['hilulot', q], queryFn: () => get('/hilulot' + (q ? '?q=' + encodeURIComponent(q) : '')) })
  const active = useQuery({ queryKey: ['hilulot-active'], queryFn: () => get('/hilulot/active') })
  const sorted = [...data].sort((a, b) => (a.dates[0]?.next_date || '9').localeCompare(b.dates[0]?.next_date || '9'))
  return (
    <div>
      <PageHeader title="ימי הילולה" subtitle="צדיקים, תאריך הילולה עברי, תולדות חייו וקטע לימוד מתורתו" actions={<Btn kind="primary" icon="plus" onClick={() => setEditing(blank())}>צדיק חדש</Btn>} />
      {dialog}
      {active.data?.items?.length > 0 && <div className="banner gold"><Icon name="star" /> היום ({active.data.hebrew_date}): {active.data.items.map((t: any) => [t.honorific, t.display_name].filter(Boolean).join(' ')).join(', ')}</div>}
      <Card>
        <div className="toolbar"><SearchBox value={q} onChange={setQ} placeholder="חיפוש צדיק" /></div>
        <ErrorBox error={error} />
        {isLoading ? <Loading /> : !sorted.length ? <Empty>אין צדיקים במאגר</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr><th></th><th>שם</th><th>תאריך עברי</th><th>הבא</th><th>מצב</th><th></th></tr></thead>
            <tbody>{sorted.map(t => (
              <tr key={t.id} className={t.is_active ? '' : 'disabled'}>
                <td>{t.image_url ? <img className="thumb" src={t.image_url} alt="" /> : <span className="thumb none"><Icon name="star" size={16} /></span>}</td>
                <td><strong>{[t.honorific, t.display_name].filter(Boolean).join(' ')}</strong>{t.burial_place && <small className="muted"> · {t.burial_place}</small>}</td>
                <td>{t.dates.map(d => d.hebrew_date_str).join(', ')}</td>
                <td>{t.dates[0]?.next_date ? fmtDate(t.dates[0].next_date) : ''}</td>
                <td>{t.is_active ? <Badge tone="ok">פעיל</Badge> : <Badge tone="off">כבוי</Badge>}{t.image_url ? <Badge>עם תמונה</Badge> : <Badge>ללא תמונה</Badge>}</td>
                <td className="row-actions">
                  <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditing(t)}><Icon name="edit" size={18} /></button>
                  <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm(`למחוק את ${t.display_name}?`)) { await del(`/hilulot/${t.id}`); qc.invalidateQueries({ queryKey: ['hilulot'] }); toast('נמחק') } }}><Icon name="trash" size={18} /></button>
                </td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Card>
      {editing && <TzForm initial={editing} onClose={() => setEditing(null)} />}
    </div>
  )
}

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { get, put } from '../api'
import { useAuth } from '../main'
import { Btn, Card, CheckList, ErrorBox, Field, Loading, PageHeader, Select, Toggle, useToast } from '../ui'

export function useSettingsForm() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['settings'], queryFn: () => get('/settings') })
  const [s, setS] = useState<any>(null)
  useEffect(() => { if (q.data) setS(structuredClone(q.data)) }, [q.data])
  const save = useMutation({
    mutationFn: () => {
      const keys = ['name', 'logo_asset_id', 'address', 'city', 'latitude', 'longitude', 'elevation_m', 'timezone', 'in_israel', 'walled_city_purim', 'nusach', 'day_change', 'day30_policy', 'show_national_holidays', 'prayer_additions', 'reminders', 'daily_learning', 'footer_text', 'theme']
      const pkeys = ['alos_method', 'misheyakir_degrees', 'tzeit_method', 'candle_lighting_minutes', 'shabbat_end_method', 'shabbat_end_minutes', 'rabbeinu_tam_minutes', 'rabbeinu_tam_zmaniyot', 'use_elevation', 'enabled_zmanim']
      const body: any = Object.fromEntries(keys.map(k => [k, s[k]]))
      body.profile = Object.fromEntries(pkeys.map(k => [k, s.profile[k]]))
      return put('/settings', body)
    },
    onSuccess: () => { qc.invalidateQueries(); toast('ההגדרות נשמרו — התצוגה תתעדכן אוטומטית') },
    onError: (e: Error) => toast(e.message, 'error'),
  })
  return { s, setS, save, loading: q.isLoading, error: q.error }
}

function Section({ title, children, open: initial = false }: { title: string; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(initial)
  return (
    <section className={'accordion' + (open ? ' open' : '')}>
      <button type="button" className="acc-head" aria-expanded={open} onClick={() => setOpen(!open)}><span>{title}</span><span className="acc-sign" aria-hidden="true">{open ? '−' : '+'}</span></button>
      {open && <div className="acc-body">{children}</div>}
    </section>
  )
}

export default function Zmanim() {
  const { me } = useAuth()
  const { s, setS, save, loading, error } = useSettingsForm()
  const { data: opt } = useQuery({ queryKey: ['options'], queryFn: () => get('/settings/options') })
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10))
  const range = useQuery({ queryKey: ['zmanim-range', start, s?.updated_at], queryFn: () => get(`/zmanim/range?start=${start}&days=7`) })
  if (loading || !s || !opt) return <Loading />
  const p = s.profile
  const setP = (x: any) => setS({ ...s, profile: { ...p, ...x } })
  const isAdmin = me.role === 'admin'
  const enabled = opt.zmanim.filter((z: any) => p.enabled_zmanim.includes(z.key))
  return (
    <div>
      <PageHeader title="זמני היום" subtitle={<>חישוב לפי מיקום בית הכנסת ({s.latitude.toFixed(3)}, {s.longitude.toFixed(3)}), אזור זמן {s.timezone}. מנוע: {opt.engine}</>}
        actions={isAdmin && <Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending}>שמירה</Btn>} />
      <ErrorBox error={error} />
      {!isAdmin && <div className="banner">צפייה בלבד — שינוי הגדרות חישוב מותר למנהל.</div>}
      <div className="two-col">
        <div>
          <Card>
            <Field label="עדה / נוסח" hint="משפיע על סליחות, ברכת הלבנה ועוד">
              <Select value={s.nusach} onChange={v => setS({ ...s, nusach: v })} options={opt.nusachim} />
            </Field>
          </Card>
          <Section title="זמני היום המוצגים" open>
            <CheckList columns={2} options={opt.zmanim} value={p.enabled_zmanim} onChange={v => setP({ enabled_zmanim: v })} />
            <small className="hint">זמנים כמו הדלקת נרות, צאת שבת, תחילת/סוף צום וזמני חמץ מופיעים רק בימים הרלוונטיים.</small>
          </Section>
          <Section title="שיטות חישוב">
            <p className="hint">כל אחת מההגדרות היא בחירה הלכתית הניתנת לשינוי — יש להתאים לפסק הרב המקומי.</p>
            <div className="grid2">
              <Field label="עלות השחר"><Select value={p.alos_method} onChange={v => setP({ alos_method: v })} options={[{ key: '72min', label: '72 דקות לפני הזריחה' }, { key: '90min', label: '90 דקות לפני הזריחה' }, { key: '16.1deg', label: '16.1° מתחת לאופק' }, { key: '19.8deg', label: '19.8° מתחת לאופק' }]} /></Field>
              <Field label="טלית ותפילין (מעלות)"><input type="number" step="0.1" min={9} max={13} value={p.misheyakir_degrees} onChange={e => setP({ misheyakir_degrees: +e.target.value })} /></Field>
              <Field label="צאת הכוכבים"><Select value={p.tzeit_method} onChange={v => setP({ tzeit_method: v })} options={[{ key: '8.5deg', label: '8.5° (גאונים)' }, { key: '7.083deg', label: '7.083°' }, { key: '13.5min_zmaniyot', label: '13.5 דקות זמניות' }, { key: '18min', label: '18 דקות' }, { key: '20min', label: '20 דקות' }]} /></Field>
              <Field label="הדלקת נרות — דקות לפני השקיעה"><input type="number" min={0} max={60} value={p.candle_lighting_minutes} onChange={e => setP({ candle_lighting_minutes: +e.target.value })} /></Field>
              <Field label="צאת שבת וחג"><Select value={p.shabbat_end_method} onChange={v => setP({ shabbat_end_method: v })} options={[{ key: 'tzeit', label: 'לפי צאת הכוכבים' }, { key: 'minutes_after_sunset', label: 'מספר דקות אחרי השקיעה' }]} /></Field>
              {p.shabbat_end_method === 'minutes_after_sunset' && <Field label="דקות אחרי השקיעה"><input type="number" min={0} max={120} value={p.shabbat_end_minutes} onChange={e => setP({ shabbat_end_minutes: +e.target.value })} /></Field>}
              <Field label="רבנו תם — דקות"><input type="number" min={50} max={120} value={p.rabbeinu_tam_minutes} onChange={e => setP({ rabbeinu_tam_minutes: +e.target.value })} /></Field>
              <Field label="רבנו תם"><Select value={p.rabbeinu_tam_zmaniyot ? 'z' : 's'} onChange={v => setP({ rabbeinu_tam_zmaniyot: v === 'z' })} options={[{ key: 'z', label: 'דקות זמניות' }, { key: 's', label: 'דקות שוות' }]} /></Field>
            </div>
            <Toggle checked={p.use_elevation} onChange={v => setP({ use_elevation: v })} label="חישוב זריחה ושקיעה לפי גובה המקום (אחרת — מישורי)" />
            <p className="hint">זריחה/שקיעה "נראית" (לפי תוואי השטח) אינה נתמכת — דורשת נתוני טופוגרפיה. הזמנים מעוגלים לחומרה: זמני התחלה כלפי מעלה, זמני סוף כלפי מטה.</p>
          </Section>
          <Section title="פרטי היום — הוספות ושינויים בתפילה">
            <CheckList columns={2} options={opt.additions} value={s.prayer_additions} onChange={v => setS({ ...s, prayer_additions: v })} />
            <small className="hint">הכללים לפי המנהג הנפוץ; ניתן לבטל כל פריט שאינו מתאים למנהג בית הכנסת.</small>
          </Section>
          <Section title="תזכורות">
            <CheckList columns={2} options={opt.reminders} value={s.reminders} onChange={v => setS({ ...s, reminders: v })} />
          </Section>
          <Section title="לימוד יומי">
            <CheckList columns={1} options={opt.learning} value={s.daily_learning} onChange={v => setS({ ...s, daily_learning: v })} />
          </Section>
        </div>
        <Card title="זמנים לשבוע" actions={<input type="date" aria-label="תאריך התחלה" value={start} onChange={e => setStart(e.target.value)} />}>
          {range.isLoading ? <Loading /> : (
            <div className="table-wrap"><table className="zm-table">
              <thead><tr><th>זמן</th>{range.data?.map((d: any) => <th key={d.date}>{new Date(d.date).toLocaleDateString('he-IL', { weekday: 'short', day: 'numeric', month: 'numeric' })}<br /><small>{d.hebrew.split(' ').slice(0, 2).join(' ')}</small></th>)}</tr></thead>
              <tbody>{enabled.map((z: any) => (
                <tr key={z.key}><th>{z.label}</th>{range.data?.map((d: any) => <td key={d.date}>{d.z[z.key] || ''}</td>)}</tr>
              ))}</tbody>
            </table></div>
          )}
          <small className="hint">הטבלה מוצגת לפי ההגדרות השמורות. לאחר שמירה התצוגה מתעדכנת.</small>
        </Card>
      </div>
    </div>
  )
}

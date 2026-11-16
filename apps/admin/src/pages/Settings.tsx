import { useAuth } from '../main'
import { Btn, Card, ErrorBox, Field, ImagePicker, Loading, PageHeader, Select, Toggle } from '../ui'
import { useSettingsForm } from './Zmanim'

const PRESETS = [
  { key: 'jerusalem', label: 'ירושלים', lat: 31.778, lon: 35.235, el: 754 },
  { key: 'telaviv', label: 'תל אביב', lat: 32.0853, lon: 34.7818, el: 20 },
  { key: 'haifa', label: 'חיפה', lat: 32.794, lon: 34.9896, el: 50 },
  { key: 'beersheva', label: 'באר שבע', lat: 31.2518, lon: 34.7913, el: 260 },
  { key: 'bneibrak', label: 'בני ברק', lat: 32.0807, lon: 34.8338, el: 30 },
  { key: 'safed', label: 'צפת', lat: 32.9646, lon: 35.496, el: 850 },
]

export default function Settings() {
  const { me } = useAuth()
  const { s, setS, save, loading, error } = useSettingsForm()
  if (loading || !s) return <Loading />
  const ro = me.role !== 'admin'
  const theme = s.theme || {}
  return (
    <div>
      <PageHeader title="הגדרות כלליות" subtitle="פרטי בית הכנסת, מיקום לחישוב זמנים והגדרות תצוגה"
        actions={!ro && <Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending}>שמירה</Btn>} />
      <ErrorBox error={error} />
      {ro && <div className="banner">צפייה בלבד — שינוי הגדרות מותר למנהל.</div>}
      <fieldset disabled={ro} className="plain">
        <Card title="בית הכנסת">
          <div className="grid2">
            <Field label="שם בית הכנסת"><input value={s.name} onChange={e => setS({ ...s, name: e.target.value })} /></Field>
            <Field label="עיר"><input value={s.city || ''} onChange={e => setS({ ...s, city: e.target.value || null })} /></Field>
            <Field label="כתובת" wide><input value={s.address || ''} onChange={e => setS({ ...s, address: e.target.value || null })} /></Field>
          </div>
          <Field label="לוגו"><ImagePicker value={s.logo_asset_id} onChange={id => setS({ ...s, logo_asset_id: id })} /></Field>
          <Field label="שורת כיתוב תחתונה בלוח" hint="מוצגת כשאין הקדשה פעילה לשורה התחתונה"><input value={s.footer_text || ''} maxLength={500} onChange={e => setS({ ...s, footer_text: e.target.value || null })} /></Field>
        </Card>
        <Card title="מיקום לחישוב זמני היום">
          <div className="toolbar">מילוי מהיר: {PRESETS.map(p => <Btn key={p.key} kind="ghost" onClick={() => setS({ ...s, latitude: p.lat, longitude: p.lon, elevation_m: p.el, timezone: 'Asia/Jerusalem', in_israel: true })}>{p.label}</Btn>)}</div>
          <div className="grid4">
            <Field label="קו רוחב"><input type="number" step="0.0001" value={s.latitude} onChange={e => setS({ ...s, latitude: +e.target.value })} /></Field>
            <Field label="קו אורך"><input type="number" step="0.0001" value={s.longitude} onChange={e => setS({ ...s, longitude: +e.target.value })} /></Field>
            <Field label="גובה (מטר)"><input type="number" value={s.elevation_m} onChange={e => setS({ ...s, elevation_m: +e.target.value })} /></Field>
            <Field label="אזור זמן"><input value={s.timezone} onChange={e => setS({ ...s, timezone: e.target.value })} /></Field>
          </div>
          <div className="grid2">
            <Toggle checked={s.in_israel} onChange={v => setS({ ...s, in_israel: v })} label="בית הכנסת בארץ ישראל (יום טוב אחד, פרשיות א״י)" />
            <Toggle checked={s.walled_city_purim} onChange={v => setS({ ...s, walled_city_purim: v })} label="עיר מוקפת חומה (פורים בט״ו)" />
          </div>
        </Card>
        <Card title="לוח שנה">
          <div className="grid2">
            <Field label="חילופי יום עברי על בסיס" hint="משפיע על התאריך העברי, ימי הילולה ואזכרות בלוח">
              <Select value={s.day_change} onChange={v => setS({ ...s, day_change: v })} options={[{ key: 'sunset', label: 'שקיעה' }, { key: 'midnight', label: '24:00 (חצות)' }]} />
            </Field>
            <Field label="יום ל׳ בחודש חסר (חשון/כסלו)" hint="מדיניות מפורשת לאזכרות והילולות — יש לקבוע לפי פסק הרב">
              <Select value={s.day30_policy} onChange={v => setS({ ...s, day30_policy: v })} options={[{ key: 'last_day', label: 'ביום כ״ט של אותו חודש' }, { key: 'next_day', label: 'בא׳ של החודש הבא' }]} />
            </Field>
          </div>
          <Toggle checked={s.show_national_holidays} onChange={v => setS({ ...s, show_national_holidays: v })} label="הצגת חגים לאומיים (יום העצמאות, יום ירושלים וכו׳)" />
        </Card>
        <Card title="עיצוב התצוגה">
          <div className="grid4">
            <Field label="צבע ראשי"><input type="color" value={theme.primary || '#14304a'} onChange={e => setS({ ...s, theme: { ...theme, primary: e.target.value } })} /></Field>
            <Field label="צבע הדגשה"><input type="color" value={theme.accent || '#c9a45c'} onChange={e => setS({ ...s, theme: { ...theme, accent: e.target.value } })} /></Field>
            <Field label="רקע"><Select value={theme.background || 'night'} onChange={v => setS({ ...s, theme: { ...theme, background: v } })} options={[{ key: 'night', label: 'כחול לילה' }, { key: 'sky', label: 'שמיים' }, { key: 'stone', label: 'אבן ירושלמית' }]} /></Field>
            <Field label="גודל טקסט"><Select value={String(theme.font_scale || 1)} onChange={v => setS({ ...s, theme: { ...theme, font_scale: +v } })} options={[{ key: '0.9', label: 'קטן' }, { key: '1', label: 'רגיל' }, { key: '1.1', label: 'גדול' }]} /></Field>
          </div>
        </Card>
      </fieldset>
    </div>
  )
}

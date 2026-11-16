import { Badge, fmtDate } from '../ui'
import EntityPage from './EntityPage'

export default function Memorials() {
  return <EntityPage title="עילוי נשמת" subtitle="שמות לעילוי נשמת לפי תאריך פטירה עברי, עם תזכורת לאזכרה (יארצייט)" path="/memorials" newLabel="שם חדש"
    searchKeys={['full_name', 'parent_name']}
    blank={() => ({ full_name: '', parent_name: '', gender: 'm', hebrew_day: 1, hebrew_month: 7, hebrew_year: null, gregorian_date: null, leap_year_policy: 'adar_ii', notes: '', permanent: true, show_days_before: 7, enabled: true, screen_ids: [] })}
    fields={[
      { key: 'full_name', label: 'שם הנפטר/ת', type: 'text', required: true },
      { key: 'parent_name', label: 'שם האב / האם', type: 'text' },
      { key: 'gender', label: 'מין', type: 'select', options: [{ key: 'm', label: 'זכר (בן)' }, { key: 'f', label: 'נקבה (בת)' }] },
      { key: 'hd', label: 'תאריך פטירה עברי', type: 'hebrew', monthKey: 'hebrew_month', dayKey: 'hebrew_day', leapKey: 'leap_year_policy' },
      { key: 'hebrew_year', label: 'שנת פטירה עברית (מספר, אופציונלי)', type: 'number', hint: 'לדוגמה 5784' },
      { key: 'gregorian_date', label: 'תאריך לועזי (אופציונלי)', type: 'date' },
      { key: 'show_days_before', label: 'תזכורת אזכרה — ימים מראש', type: 'number' },
      { key: 'notes', label: 'הערות', type: 'textarea' },
      { key: 'permanent', label: 'הצגה קבועה בלוח הזיכרון', type: 'toggle' },
      { key: 'enabled', label: 'פעיל', type: 'toggle' },
      { key: 'screen_ids', label: 'שיוך למסך', type: 'screens', screenTypes: ['memorials'] },
    ]}
    columns={[
      { label: 'שם', render: r => <strong>{r.full_name} {r.gender === 'f' ? 'בת' : 'בן'} {r.parent_name}</strong> },
      { label: 'תאריך פטירה', render: r => r.hebrew_date_str },
      { label: 'אזכרה הבאה', render: r => fmtDate(r.next_yahrzeit) },
      { label: 'הצגה', render: r => r.permanent ? <Badge tone="gold">קבוע</Badge> : <Badge>בשבוע האזכרה</Badge> },
    ]} />
}

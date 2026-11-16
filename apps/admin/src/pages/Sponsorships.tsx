import { Badge, fmtDate } from '../ui'
import EntityPage from './EntityPage'

const TYPES = [
  { key: 'iluy_nishmat', label: 'לעילוי נשמת' }, { key: 'refua', label: 'לרפואת' }, { key: 'hatzlacha', label: 'להצלחת' },
  { key: 'nidvat', label: 'נדבת' }, { key: 'zivug', label: 'לזיווג הגון' }, { key: 'custom', label: 'נוסח חופשי' },
]
export default function Sponsorships() {
  return <EntityPage title="פרנסים והקדשות" subtitle="פרנס היום / השבוע / החודש / השנה — מוצג במסך הפרנסים ובשורה התחתונה" path="/sponsorships" newLabel="הקדשה חדשה"
    searchKeys={['sponsor_name', 'honoree_name', 'text']}
    blank={() => ({ sponsor_name: '', dedication_type: 'iluy_nishmat', honoree_name: '', text: '', period: 'week', start_date: new Date().toISOString().slice(0, 10), end_date: null, show_in_footer: true, enabled: true, screen_ids: [] })}
    fields={[
      { key: 'dedication_type', label: 'סוג ההקדשה', type: 'select', options: TYPES },
      { key: 'honoree_name', label: 'שם (למי ההקדשה)', type: 'text' },
      { key: 'sponsor_name', label: 'שם התורם / המשפחה', type: 'text' },
      { key: 'period', label: 'תקופה', type: 'select', options: [{ key: 'day', label: 'פרנס היום' }, { key: 'week', label: 'פרנס השבוע' }, { key: 'month', label: 'פרנס החודש' }, { key: 'year', label: 'פרנס השנה' }] },
      { key: 'start_date', label: 'מתאריך', type: 'date', required: true },
      { key: 'end_date', label: 'עד תאריך', type: 'date', hint: 'ריק = לפי התקופה' },
      { key: 'text', label: 'נוסח נוסף', type: 'textarea' },
      { key: 'show_in_footer', label: 'הצגה בשורה התחתונה של הלוח', type: 'toggle' },
      { key: 'enabled', label: 'פעיל', type: 'toggle' },
      { key: 'screen_ids', label: 'שיוך למסך', type: 'screens', screenTypes: ['sponsors', 'combined'] },
    ]}
    columns={[
      { label: 'הקדשה', render: r => <strong>{TYPES.find(t => t.key === r.dedication_type)?.label} {r.honoree_name}</strong> },
      { label: 'תורם', render: r => r.sponsor_name },
      { label: 'תוקף', render: r => `${fmtDate(r.start_date)} – ${fmtDate(r.effective_end)}` },
      { label: 'מצב', render: r => r.is_active_now ? <Badge tone="ok">פעיל כעת</Badge> : <Badge tone="off">לא בתוקף</Badge> },
    ]} />
}

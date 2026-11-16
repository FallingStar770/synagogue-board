import { fmtDate } from '../ui'
import EntityPage from './EntityPage'

export default function Birthdays() {
  return <EntityPage title="ימי הולדת" subtitle="ברכות יום הולדת לפי תאריך עברי" path="/birthdays" newLabel="יום הולדת חדש" searchKeys={['name']}
    blank={() => ({ name: '', hebrew_day: 1, hebrew_month: 7, gregorian_date: null, message: 'מזל טוב!', leap_year_policy: 'adar_ii', enabled: true })}
    fields={[
      { key: 'name', label: 'שם', type: 'text', required: true },
      { key: 'hd', label: 'תאריך לידה עברי', type: 'hebrew', monthKey: 'hebrew_month', dayKey: 'hebrew_day', leapKey: 'leap_year_policy' },
      { key: 'gregorian_date', label: 'תאריך לועזי (אופציונלי)', type: 'date' },
      { key: 'message', label: 'ברכה', type: 'text' },
      { key: 'enabled', label: 'פעיל', type: 'toggle' },
    ]}
    columns={[
      { label: 'שם', render: r => <strong>{r.name}</strong> },
      { label: 'תאריך עברי', render: r => r.hebrew_date_str },
      { label: 'הבא', render: r => fmtDate(r.next_date) },
      { label: 'ברכה', render: r => r.message },
    ]} />
}

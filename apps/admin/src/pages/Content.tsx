import { Badge } from '../ui'
import EntityPage from './EntityPage'

const KINDS = [{ key: 'story', label: 'סיפור' }, { key: 'dvar_torah', label: 'דבר תורה' }, { key: 'parsha', label: 'פרשת השבוע' }, { key: 'other', label: 'אחר' }]
export default function Content() {
  return <EntityPage title="תוכן תורני" subtitle="סיפורים, דברי תורה ותוכן לפרשת השבוע — ממקורות מורשים בלבד" path="/content" newLabel="תוכן חדש" searchKeys={['title', 'body']}
    blank={() => ({ kind: 'dvar_torah', title: '', body: '', source: '', license: '', start_date: null, end_date: null, enabled: true, sort_order: 0, screen_ids: [] })}
    fields={[
      { key: 'kind', label: 'סוג', type: 'select', options: KINDS },
      { key: 'title', label: 'כותרת', type: 'text', required: true },
      { key: 'body', label: 'תוכן', type: 'textarea' },
      { key: 'source', label: 'מקור / ייחוס', type: 'text' },
      { key: 'license', label: 'רישיון / הרשאה', type: 'text' },
      { key: 'start_date', label: 'מתאריך', type: 'date' },
      { key: 'end_date', label: 'עד תאריך', type: 'date' },
      { key: 'sort_order', label: 'סדר', type: 'number' },
      { key: 'enabled', label: 'פעיל', type: 'toggle' },
      { key: 'screen_ids', label: 'שיוך למסך', type: 'screens', screenTypes: ['content', 'combined'] },
    ]}
    columns={[
      { label: 'כותרת', render: r => <strong>{r.title}</strong> },
      { label: 'סוג', render: r => <Badge>{KINDS.find(k => k.key === r.kind)?.label}</Badge> },
      { label: 'מקור', render: r => r.source },
    ]} />
}

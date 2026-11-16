import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, del, get, patch, post, put } from '../api'
import { Badge, Btn, Card, CheckList, Empty, ErrorBox, Field, Icon, Loading, Modal, PageHeader, SearchBox, Select, Toggle, useConfirm, useToast } from '../ui'

const TABS = [['list', 'הלכות'], ['sources', 'ספרים ומקורות'], ['select', 'בחירה והצגה'], ['import', 'ייבוא'], ['history', 'היסטוריית הצגה']] as const

function SourceForm({ initial, onClose }: { initial: any; onClose: () => void }) {
  const [s, setS] = useState(initial)
  const qc = useQueryClient()
  const save = useMutation({
    mutationFn: () => { const b = { title: s.title, author: s.author, license: s.license, attribution: s.attribution, source_url: s.source_url, is_sample: s.is_sample, enabled: s.enabled }; return s.id ? patch(`/halacha-sources/${s.id}`, b) : post('/halacha-sources', b) },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['halacha-sources'] }); onClose() },
  })
  return (
    <Modal title={s.id ? 'עריכת מקור' : 'ספר / מקור חדש'} onClose={onClose} footer={<><Btn kind="primary" onClick={() => save.mutate()} disabled={!s.title || !s.license}>שמירה</Btn><Btn onClick={onClose}>ביטול</Btn></>}>
      <ErrorBox error={save.error} />
      <Field label="שם הספר / המאגר"><input value={s.title} onChange={e => setS({ ...s, title: e.target.value })} /></Field>
      <Field label="מחבר"><input value={s.author || ''} onChange={e => setS({ ...s, author: e.target.value || null })} /></Field>
      <Field label="רישיון / הרשאת שימוש (חובה)" hint="לדוגמה: נחלת הכלל, CC-BY, אישור בכתב מבעל הזכויות"><input value={s.license} onChange={e => setS({ ...s, license: e.target.value })} /></Field>
      <Field label="ייחוס להצגה"><textarea rows={2} value={s.attribution || ''} onChange={e => setS({ ...s, attribution: e.target.value || null })} /></Field>
      <Field label="קישור למקור"><input type="url" value={s.source_url || ''} onChange={e => setS({ ...s, source_url: e.target.value || null })} /></Field>
      <Toggle checked={s.enabled} onChange={v => setS({ ...s, enabled: v })} label="פעיל" />
    </Modal>
  )
}

function HalachaForm({ initial, sources, categories, onClose }: { initial: any; sources: any[]; categories: any[]; onClose: () => void }) {
  const [h, setH] = useState({ ...initial, tags: (initial.tags || []).join(', ') })
  const qc = useQueryClient()
  const { data: chapters = [] } = useQuery<any[]>({ queryKey: ['chapters', h.source_id], queryFn: () => get('/halacha-chapters?source_id=' + h.source_id), enabled: !!h.source_id })
  const save = useMutation({
    mutationFn: () => {
      const b = { source_id: h.source_id, chapter_id: h.chapter_id || null, category_id: h.category_id || null, title: h.title, text: h.text, source_ref: h.source_ref || null, sort_order: h.sort_order || 0, enabled: h.enabled, tags: h.tags.split(',').map((t: string) => t.trim()).filter(Boolean) }
      return h.id ? patch(`/halachot/${h.id}`, b) : post('/halachot', b)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['halachot'] }); qc.invalidateQueries({ queryKey: ['halacha-sources'] }); onClose() },
  })
  return (
    <Modal wide title={h.id ? 'עריכת הלכה' : 'הלכה חדשה'} onClose={onClose} footer={<><Btn kind="primary" onClick={() => save.mutate()} disabled={!h.title || !h.text || !h.source_id}>שמירה</Btn><Btn onClick={onClose}>ביטול</Btn></>}>
      <ErrorBox error={save.error} />
      <div className="grid3">
        <Field label="ספר / מקור"><Select value={h.source_id} onChange={v => setH({ ...h, source_id: v, chapter_id: null })} placeholder="בחירה…" options={sources.map(s => ({ key: s.id, label: s.title }))} /></Field>
        <Field label="פרק"><Select value={h.chapter_id} onChange={v => setH({ ...h, chapter_id: v || null })} placeholder="—" options={chapters.map(c => ({ key: c.id, label: c.title }))} /></Field>
        <Field label="נושא"><Select value={h.category_id} onChange={v => setH({ ...h, category_id: v || null })} placeholder="—" options={categories.map(c => ({ key: c.id, label: c.name }))} /></Field>
      </div>
      <Field label="כותרת"><input value={h.title} onChange={e => setH({ ...h, title: e.target.value })} /></Field>
      <Field label="טקסט ההלכה"><textarea rows={7} value={h.text} onChange={e => setH({ ...h, text: e.target.value })} /></Field>
      <div className="grid3">
        <Field label="מראה מקום"><input value={h.source_ref || ''} onChange={e => setH({ ...h, source_ref: e.target.value })} /></Field>
        <Field label="תגיות (מופרדות בפסיק)"><input value={h.tags} onChange={e => setH({ ...h, tags: e.target.value })} /></Field>
        <Field label="סדר"><input type="number" value={h.sort_order || 0} onChange={e => setH({ ...h, sort_order: +e.target.value })} /></Field>
      </div>
      <Toggle checked={h.enabled} onChange={v => setH({ ...h, enabled: v })} label="פעילה" />
    </Modal>
  )
}

function Selections({ sources, categories }: { sources: any[]; categories: any[] }) {
  const qc = useQueryClient()
  const toast = useToast()
  const { data, isLoading } = useQuery<any[]>({ queryKey: ['selections'], queryFn: () => get('/halachot/selections') })
  const { data: tags = [] } = useQuery<any[]>({ queryKey: ['halacha-tags'], queryFn: () => get('/halacha-tags') })
  const [list, setList] = useState<any[]>([])
  const [previewId, setPreviewId] = useState('')
  useEffect(() => { if (data) setList(structuredClone(data)) }, [data])
  const preview = useQuery({ queryKey: ['sel-preview', previewId, data], queryFn: () => get(`/halachot/selections/${previewId}/preview?days=7`), enabled: !!previewId })
  const save = useMutation({
    mutationFn: () => put('/halachot/selections', { selections: list.map(s => ({ id: s.id, name: s.name, mode: s.mode, source_ids: s.source_ids, category_ids: s.category_ids, chapter_ids: s.chapter_ids || [], halacha_ids: s.halacha_ids || [], tag_ids: s.tag_ids || [], per_day: s.per_day, seed: s.seed ?? 1, active: s.active })) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['selections'] }); toast('הבחירה נשמרה') },
    onError: (e: Error) => toast(e.message, 'error'),
  })
  if (isLoading) return <Loading />
  const upd = (i: number, p: any) => setList(list.map((s, j) => (j === i ? { ...s, ...p } : s)))
  return (
    <>
      <p className="muted">בחרו אילו הלכות יוצגו: לפי ספר, נושא או תגית; בסדר רציף או אקראי. ההצגה נמנעת מחזרות עד שכל ההלכות בבחירה הוצגו. כל מסך הלכות מציג את הבחירה המוגדרת בו.</p>
      {list.map((s, i) => (
        <fieldset key={s.id || i}>
          <legend>{s.name || 'בחירה חדשה'} {s.eligible_count !== undefined && <Badge>{s.eligible_count} הלכות</Badge>}</legend>
          <div className="grid4">
            <Field label="שם"><input value={s.name} onChange={e => upd(i, { name: e.target.value })} /></Field>
            <Field label="סדר הצגה"><Select value={s.mode} onChange={v => upd(i, { mode: v })} options={[{ key: 'sequential', label: 'לפי הסדר' }, { key: 'random', label: 'אקראי ללא חזרות' }]} /></Field>
            <Field label="הלכות ביום"><input type="number" min={1} max={20} value={s.per_day} onChange={e => upd(i, { per_day: +e.target.value })} /></Field>
            <Field label="מצב"><Toggle checked={s.active} onChange={v => upd(i, { active: v })} label={s.active ? 'פעילה' : 'כבויה'} /></Field>
          </div>
          <Field label="ספרים" hint="ללא סימון בכל הסינונים — כל ההלכות הפעילות"><CheckList columns={2} options={sources.map(x => ({ key: x.id, label: x.title }))} value={s.source_ids} onChange={v => upd(i, { source_ids: v })} /></Field>
          {categories.length > 0 && <Field label="נושאים"><CheckList columns={3} options={categories.map(x => ({ key: x.id, label: x.name }))} value={s.category_ids} onChange={v => upd(i, { category_ids: v })} /></Field>}
          {tags.length > 0 && <Field label="תגיות"><CheckList columns={4} options={tags.map(x => ({ key: x.id, label: x.name }))} value={s.tag_ids || []} onChange={v => upd(i, { tag_ids: v })} /></Field>}
          <div className="toolbar">
            {s.id && <Btn icon="eye" onClick={() => setPreviewId(previewId === s.id ? '' : s.id)}>תצוגה מקדימה לשבוע</Btn>}
            <Btn kind="ghost" icon="trash" onClick={() => setList(list.filter((_, j) => j !== i))}>הסרה</Btn>
          </div>
          {previewId === s.id && preview.data && <ul className="mini-list">{preview.data.map((d: any) => <li key={d.date}><strong>{new Date(d.date).toLocaleDateString('he-IL', { weekday: 'short', day: 'numeric', month: 'numeric' })}</strong> {d.halachot.map((h: any) => h.title).join(' · ') || '—'}</li>)}</ul>}
        </fieldset>
      ))}
      <div className="toolbar">
        <Btn icon="plus" onClick={() => setList([...list, { name: 'בחירה חדשה', mode: 'sequential', source_ids: [], category_ids: [], tag_ids: [], per_day: 1, active: true }])}>בחירה נוספת</Btn>
        <Btn kind="primary" icon="check" onClick={() => save.mutate()} disabled={save.isPending}>שמירת הבחירה</Btn>
      </div>
    </>
  )
}

function Import({ sources }: { sources: any[] }) {
  const [src, setSrc] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [ok, setOk] = useState(false)
  const [result, setResult] = useState<any>(null)
  const qc = useQueryClient()
  const run = useMutation({
    mutationFn: () => { const f = new FormData(); f.append('file', file!); f.append('source_id', src); f.append('confirm_license', String(ok)); return api('/halachot/import', { form: f }) },
    onSuccess: r => { setResult(r); qc.invalidateQueries({ queryKey: ['halachot'] }); qc.invalidateQueries({ queryKey: ['halacha-sources'] }) },
  })
  return (
    <>
      <p className="muted">ייבוא קובץ JSON (מערך של אובייקטים) או CSV עם העמודות: <code>title, text, source_ref, chapter, category, tags</code>. לייבוא מתוך ייצוא של ספריא (נחלת הכלל בלבד) ראו <code>scripts/sefaria_to_import.py</code>.</p>
      <div className="grid2">
        <Field label="ייבוא אל ספר / מקור"><Select value={src} onChange={setSrc} placeholder="בחירה…" options={sources.map(s => ({ key: s.id, label: `${s.title} (${s.license})` }))} /></Field>
        <Field label="קובץ"><input type="file" accept=".json,.csv,application/json,text/csv" onChange={e => setFile(e.target.files?.[0] || null)} /></Field>
      </div>
      <label className="check"><input type="checkbox" checked={ok} onChange={e => setOk(e.target.checked)} /> אני מאשר/ת שהתוכן המיובא מותר לשימוש בהתאם לרישיון המקור</label>
      <ErrorBox error={run.error} />
      <Btn kind="primary" icon="upload" disabled={!src || !file || !ok || run.isPending} onClick={() => run.mutate()}>{run.isPending ? 'מייבא…' : 'ייבוא'}</Btn>
      {result && <div className="banner">יובאו {result.created} הלכות.{result.errors.length > 0 && <> {result.errors.length} שורות נדחו: {result.errors.slice(0, 5).map((e: any) => `שורה ${e.row}: ${e.error}`).join('; ')}</>}</div>}
    </>
  )
}

export default function Halachot() {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [tab, setTab] = useState<string>('list')
  const [q, setQ] = useState('')
  const [srcF, setSrcF] = useState('')
  const [page, setPage] = useState(0)
  const [editing, setEditing] = useState<any>(null)
  const [editingSrc, setEditingSrc] = useState<any>(null)
  const { data: sources = [] } = useQuery<any[]>({ queryKey: ['halacha-sources'], queryFn: () => get('/halacha-sources') })
  const { data: categories = [] } = useQuery<any[]>({ queryKey: ['halacha-categories'], queryFn: () => get('/halacha-categories') })
  const list = useQuery({ queryKey: ['halachot', q, srcF, page], queryFn: () => get(`/halachot?limit=50&offset=${page * 50}` + (q ? '&q=' + encodeURIComponent(q) : '') + (srcF ? '&source_id=' + srcF : '')), enabled: tab === 'list' })
  const history = useQuery<any[]>({ queryKey: ['halacha-history'], queryFn: () => get('/halachot/history'), enabled: tab === 'history' })
  const [newCat, setNewCat] = useState('')
  const srcName = (id: string) => sources.find(s => s.id === id)?.title || ''
  return (
    <div>
      <PageHeader title="מאגר הלכות" subtitle="ספרים, נושאים, הלכות, ייבוא מורשה ובחירת הלכות להצגה" actions={<>
        <Btn icon="plus" onClick={() => setEditingSrc({ title: '', license: '', enabled: true, is_sample: false })}>ספר חדש</Btn>
        <Btn kind="primary" icon="plus" disabled={!sources.length} onClick={() => setEditing({ source_id: srcF || sources[0]?.id, title: '', text: '', enabled: true, tags: [] })}>הלכה חדשה</Btn>
      </>} />
      {dialog}
      <div className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</div>
      <Card>
        {tab === 'list' && <>
          <div className="toolbar">
            <SearchBox value={q} onChange={v => { setQ(v); setPage(0) }} placeholder="חיפוש הלכה" />
            <Select value={srcF} onChange={v => { setSrcF(v); setPage(0) }} placeholder="כל הספרים" options={sources.map(s => ({ key: s.id, label: s.title }))} />
          </div>
          {list.isLoading ? <Loading /> : !list.data?.items.length ? <Empty>לא נמצאו הלכות</Empty> : <>
            <div className="table-wrap"><table>
              <thead><tr><th>כותרת</th><th>ספר</th><th>מראה מקום</th><th>תגיות</th><th></th></tr></thead>
              <tbody>{list.data.items.map((h: any) => (
                <tr key={h.id} className={h.enabled ? '' : 'disabled'}>
                  <td><strong>{h.title}</strong><div className="muted clamp">{h.text}</div></td>
                  <td>{srcName(h.source_id)}</td><td>{h.source_ref}</td><td>{h.tags.map((t: string) => <Badge key={t}>{t}</Badge>)}</td>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditing(h)}><Icon name="edit" size={18} /></button>
                    <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm('למחוק הלכה זו?')) { await del(`/halachot/${h.id}`); qc.invalidateQueries({ queryKey: ['halachot'] }) } }}><Icon name="trash" size={18} /></button>
                  </td>
                </tr>))}</tbody>
            </table></div>
            <div className="pager"><Btn disabled={page === 0} onClick={() => setPage(page - 1)}>הקודם</Btn><span>{page * 50 + 1}–{Math.min((page + 1) * 50, list.data.total)} מתוך {list.data.total}</span><Btn disabled={(page + 1) * 50 >= list.data.total} onClick={() => setPage(page + 1)}>הבא</Btn></div>
          </>}
        </>}
        {tab === 'sources' && <>
          {!sources.length ? <Empty>אין ספרים. הוסיפו ספר עם פרטי רישיון.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>ספר</th><th>מחבר</th><th>רישיון</th><th>הלכות</th><th></th></tr></thead>
              <tbody>{sources.map(s => (
                <tr key={s.id} className={s.enabled ? '' : 'disabled'}>
                  <td><strong>{s.title}</strong>{s.is_sample && <Badge tone="warn">דוגמה</Badge>}</td><td>{s.author}</td><td>{s.license}</td><td>{s.count}</td>
                  <td className="row-actions">
                    <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => setEditingSrc(s)}><Icon name="edit" size={18} /></button>
                    <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm(`למחוק את "${s.title}" וכל ההלכות שבו?`)) { await del(`/halacha-sources/${s.id}`); qc.invalidateQueries() ; toast('נמחק') } }}><Icon name="trash" size={18} /></button>
                  </td>
                </tr>))}</tbody>
            </table></div>
          )}
          <fieldset><legend>נושאים</legend>
            <div className="chips">{categories.map(c => <span key={c.id} className="chip">{c.name}<button type="button" aria-label={`מחיקת ${c.name}`} onClick={async () => { await del(`/halacha-categories/${c.id}`); qc.invalidateQueries({ queryKey: ['halacha-categories'] }) }}>×</button></span>)}</div>
            <div className="toolbar"><input placeholder="נושא חדש" aria-label="נושא חדש" value={newCat} onChange={e => setNewCat(e.target.value)} /><Btn icon="plus" disabled={!newCat} onClick={async () => { try { await post('/halacha-categories', { name: newCat }); setNewCat(''); qc.invalidateQueries({ queryKey: ['halacha-categories'] }) } catch (e) { toast((e as Error).message, 'error') } }}>הוספה</Btn></div>
          </fieldset>
        </>}
        {tab === 'select' && <Selections sources={sources} categories={categories} />}
        {tab === 'import' && <Import sources={sources} />}
        {tab === 'history' && (history.isLoading ? <Loading /> : !history.data?.length ? <Empty>עדיין לא הוצגו הלכות</Empty> :
          <ul className="mini-list">{history.data.map((h, i) => <li key={i}><strong>{new Date(h.date).toLocaleDateString('he-IL')}</strong> {h.title}</li>)}</ul>)}
      </Card>
      {editing && <HalachaForm initial={editing} sources={sources} categories={categories} onClose={() => setEditing(null)} />}
      {editingSrc && <SourceForm initial={editingSrc} onClose={() => setEditingSrc(null)} />}
    </div>
  )
}

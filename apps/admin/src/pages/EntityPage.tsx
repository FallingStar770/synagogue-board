// Generic list + form page for simple content types (memorials, sponsors, birthdays, content).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { del, get, patch, post } from '../api'
import { Btn, Card, Empty, ErrorBox, Field, HebrewDateInput, Icon, Loading, Modal, PageHeader, ScreenLinks, SearchBox, Select, Toggle, useConfirm, useToast } from '../ui'
import type { Option } from '../types'

export type FieldDef =
  | { key: string; label: string; type: 'text' | 'textarea' | 'date' | 'number'; hint?: string; required?: boolean }
  | { key: string; label: string; type: 'select'; options: Option[]; hint?: string }
  | { key: string; label: string; type: 'toggle' }
  | { key: string; label: string; type: 'hebrew'; monthKey: string; dayKey: string; leapKey?: string }
  | { key: string; label: string; type: 'screens'; screenTypes: string[] }

export type Column = { label: string; render: (row: any) => React.ReactNode }

export default function EntityPage({ title, subtitle, path, fields, columns, blank, newLabel, searchKeys }: {
  title: string; subtitle: string; path: string; fields: FieldDef[]; columns: Column[]; blank: () => any; newLabel: string; searchKeys: string[]
}) {
  const qc = useQueryClient()
  const toast = useToast()
  const { confirm, dialog } = useConfirm()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<any>(null)
  const { data = [], isLoading, error } = useQuery<any[]>({ queryKey: [path], queryFn: () => get(path) })
  const rows = data.filter(r => !q || searchKeys.some(k => String(r[k] || '').includes(q)))
  const save = useMutation({
    mutationFn: (r: any) => {
      const body: any = {}
      for (const f of fields) {
        if (f.type === 'hebrew') { body[f.monthKey] = r[f.monthKey]; body[f.dayKey] = r[f.dayKey]; if (f.leapKey) body[f.leapKey] = r[f.leapKey] }
        else body[f.key] = r[f.key] === '' ? null : r[f.key]
      }
      return r.id ? patch(`${path}/${r.id}`, body) : post(path, body)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: [path] }); toast('נשמר'); setEditing(null) },
  })
  const set = (p: any) => setEditing({ ...editing, ...p })
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} actions={<Btn kind="primary" icon="plus" onClick={() => { save.reset(); setEditing(blank()) }}>{newLabel}</Btn>} />
      {dialog}
      <Card>
        <div className="toolbar"><SearchBox value={q} onChange={setQ} /></div>
        <ErrorBox error={error} />
        {isLoading ? <Loading /> : !rows.length ? <Empty>אין רשומות</Empty> : (
          <div className="table-wrap"><table>
            <thead><tr>{columns.map(c => <th key={c.label}>{c.label}</th>)}<th></th></tr></thead>
            <tbody>{rows.map(r => (
              <tr key={r.id} className={r.enabled === false ? 'disabled' : ''}>
                {columns.map(c => <td key={c.label}>{c.render(r)}</td>)}
                <td className="row-actions">
                  <button type="button" className="icon-btn" aria-label="עריכה" onClick={() => { save.reset(); setEditing(structuredClone(r)) }}><Icon name="edit" size={18} /></button>
                  <button type="button" className="icon-btn danger" aria-label="מחיקה" onClick={async () => { if (await confirm('למחוק רשומה זו?')) { await del(`${path}/${r.id}`); qc.invalidateQueries({ queryKey: [path] }); toast('נמחק') } }}><Icon name="trash" size={18} /></button>
                </td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Card>
      {editing && (
        <Modal wide title={editing.id ? 'עריכה' : newLabel} onClose={() => setEditing(null)}
          footer={<><Btn kind="primary" icon="check" disabled={save.isPending} onClick={() => save.mutate(editing)}>שמירה</Btn><Btn onClick={() => setEditing(null)}>ביטול</Btn></>}>
          <ErrorBox error={save.error} />
          <div className="form-grid">
            {fields.map(f => {
              const v = editing[f.key]
              switch (f.type) {
                case 'text': case 'date': case 'number':
                  return <Field key={f.key} label={f.label} hint={f.hint}><input type={f.type} value={v ?? ''} required={f.required} onChange={e => set({ [f.key]: f.type === 'number' ? (e.target.value === '' ? null : +e.target.value) : e.target.value })} /></Field>
                case 'textarea':
                  return <Field key={f.key} wide label={f.label} hint={f.hint}><textarea rows={4} value={v ?? ''} onChange={e => set({ [f.key]: e.target.value })} /></Field>
                case 'select':
                  return <Field key={f.key} label={f.label} hint={f.hint}><Select value={v} onChange={x => set({ [f.key]: x })} options={f.options} /></Field>
                case 'toggle':
                  return <div key={f.key} className="field"><Toggle checked={!!v} onChange={x => set({ [f.key]: x })} label={f.label} /></div>
                case 'hebrew':
                  return <Field key={f.key} wide label={f.label}><HebrewDateInput month={editing[f.monthKey]} day={editing[f.dayKey]} onChange={(m, d) => set({ [f.monthKey]: m, [f.dayKey]: d })}
                    leapPolicy={f.leapKey ? editing[f.leapKey] : undefined} onLeapPolicy={f.leapKey ? x => set({ [f.leapKey!]: x }) : undefined} /></Field>
                case 'screens':
                  return <Field key={f.key} wide label={f.label}><ScreenLinks types={f.screenTypes} value={v} onChange={x => set({ [f.key]: x })} /></Field>
              }
            })}
          </div>
        </Modal>
      )}
    </div>
  )
}

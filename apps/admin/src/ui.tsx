import React, { createContext, useContext, useEffect, useId, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { get, upload } from './api'
import { HEB_MONTHS, LEAP_POLICIES, WEEKDAYS, hebDay, type Option, type Rule, type Screen } from './types'

// ---------------------------------------------------------------- icons (inline SVG, offline-safe)
const P: Record<string, string> = {
  eye: 'M12 5c-7 0-10 7-10 7s3 7 10 7 10-7 10-7-3-7-10-7zm0 11a4 4 0 110-8 4 4 0 010 8z',
  screens: 'M3 4h18v12H3zM8 20h8M12 16v4',
  mail: 'M3 6h18v12H3zM3 6l9 7 9-7',
  clock: 'M12 3a9 9 0 100 18 9 9 0 000-18zm0 4v5l3 3',
  book: 'M4 5c3-1 6-1 8 1 2-2 5-2 8-1v13c-3-1-6-1-8 1-2-2-5-2-8-1zM12 6v13',
  candle: 'M10 10h4v11h-4zM12 3c2 2 2 4 0 5-2-1-2-3 0-5zM7 21h10',
  sun: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1',
  scroll: 'M6 4h11a3 3 0 010 6H6zM6 4a3 3 0 000 6v8a2 2 0 002 2h10M10 14h6',
  coins: 'M4 7h16v10H4zM12 9a3 3 0 100 6 3 3 0 000-6z',
  star: 'M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.5 6.7 19.4l1.2-6L3.4 9.3l6-.7z',
  cake: 'M4 11h16v9H4zM4 15c3 2 5-2 8 0s5 2 8 0M12 4v4M12 4c1 1 1 2 0 2',
  text: 'M5 5h14M5 10h14M5 15h9M5 20h12',
  tv: 'M3 5h18v12H3zM8 21l4-4 4 4',
  tools: 'M14 7l3-3 3 3-3 3M17 4L9 12M4 20l6-6M8 16l-4 4',
  gear: 'M12 9a3 3 0 100 6 3 3 0 000-6zM19 12l2-1-1-3-2 .3-1.4-1.4.3-2-3-1-1 2h-2l-1-2-3 1 .3 2L5.8 7.3 3.8 7 3 10l2 1v2l-2 1 1 3 2-.3 1.4 1.4-.3 2 3 1 1-2h2l1 2 3-1-.3-2 1.4-1.4 2 .3 1-3-2-1z',
  users: 'M9 11a4 4 0 100-8 4 4 0 000 8zM2 21c0-4 3-6 7-6s7 2 7 6M17 11a3 3 0 100-6M22 21c0-3-2-5-5-5',
  home: 'M3 11l9-8 9 8M5 10v10h14V10',
  plus: 'M12 5v14M5 12h14', edit: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4', trash: 'M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13',
  copy: 'M8 8h12v12H8zM4 16V4h12', up: 'M12 19V5M5 12l7-7 7 7', down: 'M12 5v14M5 12l7 7 7-7',
  grip: 'M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01', search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM21 21l-5-5',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11', menu: 'M4 6h16M4 12h16M4 18h16', x: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12l5 5 9-10', download: 'M12 4v12M6 10l6 6 6-6M4 20h16', upload: 'M12 20V8M6 14l6-6 6 6M4 4h16',
  image: 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9h.01', key: 'M8 14a4 4 0 110-8 4 4 0 010 8zM11 11l9 9M17 17l2-2M15 15l2-2',
  refresh: 'M20 12a8 8 0 11-3-6.2M20 4v5h-5', alert: 'M12 3l10 18H2zM12 10v5M12 18h.01', play: 'M7 4l13 8-13 8z',
}
export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="icon">
      <path d={P[name] || P.text} />
    </svg>
  )
}

// ---------------------------------------------------------------- toasts
type Toast = { id: number; text: string; kind: 'ok' | 'error' }
const ToastCtx = createContext<(text: string, kind?: 'ok' | 'error') => void>(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([])
  const push = (text: string, kind: 'ok' | 'error' = 'ok') => {
    const id = Date.now() + Math.random()
    setItems(x => [...x, { id, text, kind }])
    setTimeout(() => setItems(x => x.filter(t => t.id !== id)), kind === 'error' ? 7000 : 3500)
  }
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map(t => <div key={t.id} className={'toast ' + t.kind}>{t.kind === 'ok' ? <Icon name="check" /> : <Icon name="alert" />}{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  )
}

// ---------------------------------------------------------------- layout primitives
export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="page-header">
      <div><h1>{title}</h1>{subtitle && <p className="muted">{subtitle}</p>}</div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  )
}
export function Card({ title, children, actions, className = '' }: { title?: React.ReactNode; children: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <section className={'card ' + className}>
      {(title || actions) && <div className="card-head">{title && <h2>{title}</h2>}{actions}</div>}
      {children}
    </section>
  )
}
export function Btn({ icon, children, kind = 'secondary', ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: string; kind?: 'primary' | 'secondary' | 'danger' | 'ghost' }) {
  return <button type="button" className={'btn ' + kind} {...rest}>{icon && <Icon name={icon} size={18} />}{children}</button>
}
export function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'ok' | 'warn' | 'off' | 'neutral' | 'gold' }) {
  return <span className={'badge ' + tone}>{children}</span>
}
export function Empty({ children }: { children: React.ReactNode }) { return <div className="empty">{children}</div> }
export function Loading() { return <div className="loading" aria-busy="true"><span /><span /><span /></div> }
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null
  return <div className="error-box" role="alert"><Icon name="alert" /> {(error as Error).message}</div>
}

// ---------------------------------------------------------------- form fields
export function Field({ label, hint, children, wide }: { label: string; hint?: React.ReactNode; children: React.ReactNode; wide?: boolean }) {
  const id = useId()
  const child = React.isValidElement(children) ? React.cloneElement(children as React.ReactElement<any>, { id }) : children
  return (
    <div className={'field' + (wide ? ' wide' : '')}>
      <label htmlFor={id}>{label}</label>
      {child}
      {hint && <small className="hint">{hint}</small>}
    </div>
  )
}
export function Toggle({ checked, onChange, label, id }: { checked: boolean; onChange: (v: boolean) => void; label?: string; id?: string }) {
  return (
    <label className="toggle">
      <input id={id} type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      <span className="track"><span className="thumb" /></span>
      {label && <span>{label}</span>}
    </label>
  )
}
export function Select({ value, onChange, options, placeholder, id }: { value: string | null | undefined; onChange: (v: string) => void; options: Option[]; placeholder?: string; id?: string }) {
  return (
    <select id={id} value={value ?? ''} onChange={e => onChange(e.target.value)}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map(o => <option key={o.key} value={o.key}>{o.label}</option>)}
    </select>
  )
}
export function CheckList({ options, value, onChange, columns = 2 }: { options: Option[]; value: string[]; onChange: (v: string[]) => void; columns?: number }) {
  return (
    <div className="checklist" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0,1fr))` }}>
      {options.map(o => (
        <label key={o.key} className="check">
          <input type="checkbox" checked={value.includes(o.key)}
            onChange={e => onChange(e.target.checked ? [...value, o.key] : value.filter(x => x !== o.key))} />
          <span>{o.label}</span>
        </label>
      ))}
    </div>
  )
}
export function WeekdayPicker({ value, onChange }: { value: number[]; onChange: (v: number[]) => void }) {
  return (
    <div className="weekdays" role="group" aria-label="ימים בשבוע">
      {WEEKDAYS.map((d, i) => (
        <button key={i} type="button" aria-pressed={value.includes(i)} className={value.includes(i) ? 'on' : ''}
          onClick={() => onChange(value.includes(i) ? value.filter(x => x !== i) : [...value, i].sort())}>{d}</button>
      ))}
    </div>
  )
}

export function HebrewDateInput({ month, day, onChange, leapPolicy, onLeapPolicy }: {
  month: number; day: number; onChange: (m: number, d: number) => void; leapPolicy?: string; onLeapPolicy?: (v: string) => void
}) {
  const [greg, setGreg] = useState('')
  const convert = async (v: string) => {
    setGreg(v)
    if (!v) return
    try {
      const r = await get(`/hebrew-date?date=${v}`)
      onChange(r.month, r.day)
    } catch { /* ignore */ }
  }
  return (
    <div className="hebdate">
      <div className="row">
        <select aria-label="יום" value={day} onChange={e => onChange(month, +e.target.value)}>
          {Array.from({ length: 30 }, (_, i) => <option key={i} value={i + 1}>{hebDay(i + 1)}</option>)}
        </select>
        <select aria-label="חודש" value={month} onChange={e => onChange(+e.target.value, day)}>
          {HEB_MONTHS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
        </select>
        <label className="greg">או לפי תאריך לועזי: <input type="date" value={greg} onChange={e => convert(e.target.value)} /></label>
      </div>
      {onLeapPolicy && (month === 12 || month === 13) && (
        <select aria-label="מדיניות שנה מעוברת" value={leapPolicy} onChange={e => onLeapPolicy(e.target.value)}>
          {LEAP_POLICIES.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
        </select>
      )}
    </div>
  )
}

export function useScreens() {
  return useQuery<Screen[]>({ queryKey: ['screens'], queryFn: () => get('/screens') })
}
export function ScreenLinks({ value, onChange, types }: { value: string[] | null | undefined; onChange: (v: string[]) => void; types: string[] }) {
  const { data = [] } = useScreens()
  const relevant = data.filter(s => types.includes(s.type))
  if (!relevant.length) return <small className="hint">אין מסכים מתאימים. ניתן ליצור מסך בעמוד "מסכים".</small>
  return (
    <div>
      <CheckList columns={2} options={relevant.map(s => ({ key: s.id, label: s.name + (s.enabled ? '' : ' (כבוי)') }))}
        value={value || []} onChange={onChange} />
      <small className="hint">ללא סימון — יוצג בכל המסכים מסוג זה.</small>
    </div>
  )
}

export function ImagePicker({ value, onChange, url }: { value: string | null; onChange: (id: string | null, url: string | null) => void; url?: string | null }) {
  const ref = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const toast = useToast()
  const pick = async (f?: File) => {
    if (!f) return
    setErr('')
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(f.type)) return setErr('יש לבחור קובץ JPEG, PNG או WEBP')
    if (f.size > 5 * 1024 * 1024) return setErr('גודל מקסימלי 5MB')
    setBusy(true)
    try {
      const m = await upload(f)
      onChange(m.id, m.url)
      toast('התמונה הועלתה')
    } catch (e) { setErr((e as Error).message) } finally { setBusy(false) }
  }
  const src = url || (value ? `/api/v1/media/${value}` : null)
  return (
    <div className="imagepicker">
      {src ? <img src={src} alt="" /> : <div className="noimg"><Icon name="image" size={32} /></div>}
      <div className="col">
        <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e => pick(e.target.files?.[0])} />
        <Btn icon="upload" onClick={() => ref.current?.click()} disabled={busy}>{busy ? 'מעלה…' : value ? 'החלפת תמונה' : 'העלאת תמונה'}</Btn>
        {value && <Btn kind="ghost" icon="x" onClick={() => onChange(null, null)}>הסרה</Btn>}
        {err && <small className="err">{err}</small>}
      </div>
    </div>
  )
}

export function RuleEditor({ rule, onChange, options }: { rule: Rule; onChange: (r: Rule) => void; options: any }) {
  const set = (p: Partial<Rule>) => onChange({ ...rule, ...p })
  const special = !['daily', 'weekday', 'sun_thu', 'friday', 'shabbat', 'custom'].includes(rule.day_kind)
  return (
    <div className="rule">
      <div className="grid3">
        <Field label="ימים"><Select value={rule.day_kind} onChange={v => set({ day_kind: v })} options={options?.day_kinds || []} /></Field>
        <Field label="סוג שעה">
          <Select value={rule.time_mode} onChange={v => set({ time_mode: v as Rule['time_mode'], relative_zman: v === 'relative' ? rule.relative_zman || 'sunset' : null, fixed_time: v === 'fixed' ? rule.fixed_time || '07:00' : null })}
            options={[{ key: 'fixed', label: 'שעה קבועה' }, { key: 'relative', label: 'יחסי לזמן הלכתי' }]} />
        </Field>
        {rule.time_mode === 'fixed' ? (
          <Field label="שעה"><input type="time" value={rule.fixed_time || ''} onChange={e => set({ fixed_time: e.target.value })} required /></Field>
        ) : (
          <Field label="ביחס ל־"><Select value={rule.relative_zman} onChange={v => set({ relative_zman: v })} options={options?.anchors || []} /></Field>
        )}
      </div>
      {rule.day_kind === 'custom' && <Field label="בחירת ימים"><WeekdayPicker value={rule.days_of_week} onChange={v => set({ days_of_week: v })} /></Field>}
      {rule.time_mode === 'relative' && (
        <div className="grid3">
          <Field label="הפרש בדקות" hint="שלילי = לפני, חיובי = אחרי"><input type="number" value={rule.offset_minutes} onChange={e => set({ offset_minutes: +e.target.value })} /></Field>
          <Field label="עיגול"><Select value={rule.rounding} onChange={v => set({ rounding: v })} options={options?.rounding || []} /></Field>
        </div>
      )}
      <div className="grid3">
        <Field label="משך (דקות)"><input type="number" min={1} value={rule.duration_minutes ?? ''} onChange={e => set({ duration_minutes: e.target.value ? +e.target.value : null })} /></Field>
        <Field label="בתוקף מתאריך"><input type="date" value={rule.valid_from || ''} onChange={e => set({ valid_from: e.target.value || null })} /></Field>
        <Field label="עד תאריך"><input type="date" value={rule.valid_to || ''} onChange={e => set({ valid_to: e.target.value || null })} /></Field>
      </div>
      {special && <Toggle checked={rule.replaces_regular} onChange={v => set({ replaces_regular: v })} label="ביום זה מחליף את הזמנים הרגילים מאותו סוג" />}
    </div>
  )
}

// ---------------------------------------------------------------- modal & confirm
export function Modal({ title, onClose, children, footer, wide }: { title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null
    const first = ref.current?.querySelector<HTMLElement>('input,select,textarea,button')
    first?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    document.body.classList.add('modal-open')
    return () => { window.removeEventListener('keydown', onKey); document.body.classList.remove('modal-open'); prev?.focus() }
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className={'modal' + (wide ? ' wide' : '')} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="modal-head"><h2>{title}</h2><button type="button" className="icon-btn" aria-label="סגירה" onClick={onClose}><Icon name="x" /></button></div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function useConfirm() {
  const [state, setState] = useState<{ text: string; resolve: (v: boolean) => void } | null>(null)
  const confirm = (text: string) => new Promise<boolean>(resolve => setState({ text, resolve }))
  const dialog = state && (
    <Modal title="אישור פעולה" onClose={() => { state.resolve(false); setState(null) }}
      footer={<>
        <Btn kind="danger" onClick={() => { state.resolve(true); setState(null) }}>אישור</Btn>
        <Btn onClick={() => { state.resolve(false); setState(null) }}>ביטול</Btn>
      </>}>
      <p>{state.text}</p>
    </Modal>
  )
  return { confirm, dialog }
}

export function SearchBox({ value, onChange, placeholder = 'חיפוש…' }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="search">
      <Icon name="search" size={18} />
      <input type="search" aria-label={placeholder} placeholder={placeholder} value={value} onChange={e => onChange(e.target.value)} />
    </div>
  )
}

export const fmtDate = (s?: string | null) => (s ? new Date(s).toLocaleDateString('he-IL') : '')
export const fmtDateTime = (s?: string | null) => (s ? new Date(s).toLocaleString('he-IL', { dateStyle: 'short', timeStyle: 'short' }) : '')

import { useEffect, useMemo, useState } from 'react'
import { FitBox, splitPages } from './fit'
import {
  WEEKDAYS, announcementsFor, birthdaysFor, contentFor, dedicationText, halachotFor, hilulotFor, lessonsFor,
  logicalDay, memorialsFor, periodLabel, prayersFor, shabbatDays, sponsorsFor, type Ctx, type Day, type ScreenDef, type Snapshot, type Tzadik,
} from './logic'

export type ScreenProps = { snap: Snapshot; ctx: Ctx; screen: ScreenDef; durationMs: number }

/** Rotate through n sub-pages during the screen's display time. */
export function usePager(n: number, durationMs: number, key: unknown = null) {
  const [i, setI] = useState(0)
  useEffect(() => {
    setI(0)
    if (n <= 1) return
    const t = setInterval(() => setI(x => (x + 1) % n), Math.max(4000, durationMs / n))
    return () => clearInterval(t)
  }, [n, durationMs, key])
  return Math.min(i, Math.max(0, n - 1))
}

const chunk = <T,>(a: T[], n: number) => Array.from({ length: Math.ceil(a.length / n) }, (_, i) => a.slice(i * n, i * n + n))

function Panel({ title, children, className = '' }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={'panel ' + className}>
      {title && <h2 className="panel-title"><span>{title}</span></h2>}
      {children}
    </section>
  )
}

function ZmanimList({ snap, day, keys, max }: { snap: Snapshot; day: Day; keys?: string[]; max?: number }) {
  const list = (keys || snap.enabled_zmanim).filter(k => day.z[k]).slice(0, max || 99)
  return (
    <dl className="zlist">
      {list.map(k => <div key={k}><dt>{snap.zmanim_labels[k]}</dt><dd>{day.z[k]}</dd></div>)}
    </dl>
  )
}

function SidePanel({ snap, ctx }: { snap: Snapshot; ctx: Ctx }) {
  const d = ctx.day!
  return (
    <aside className="side">
      {d.parsha && <div className="side-parsha">פרשת {d.parsha}</div>}
      {ctx.holiday && <div className="side-holiday">{ctx.holiday}</div>}
      {d.add.length > 0 && <><h3>הוספות בתפילה</h3><ul>{d.add.slice(0, 6).map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      {d.rem.length > 0 && <><h3>תזכורות</h3><ul>{d.rem.slice(0, 3).map((a, i) => <li key={i}>{a}</li>)}</ul></>}
      <h3>זמני היום</h3>
      <ZmanimList snap={snap} day={d} keys={['alot', 'misheyakir', 'shma_gra', 'tfila_gra', 'candle_lighting', 'shabbat_end'].filter(k => snap.enabled_zmanim.includes(k))} />
    </aside>
  )
}

// ---------------------------------------------------------------- clock
export function ClockScreen({ snap, ctx, screen }: ScreenProps) {
  const d = ctx.day
  const keys: string[] = (screen.config?.zmanim as string[]) ?? ['sunrise', 'sunset', 'tzeit']
  return (
    <div className="clock-screen">
      <div className="clock-disc">
        <div className="clock-date">{ctx.hebrewLabel || '—'}</div>
        <div className="clock-time" aria-label="השעה">
          {ctx.time}{screen.config?.show_seconds !== false && <span className="clock-sec">{ctx.seconds}</span>}
        </div>
        {d && keys.length > 0 && (
          <div className="clock-zmanim">
            {keys.filter(k => d.z[k]).map(k => <span key={k}>{snap.zmanim_labels[k].replace('צאת הכוכבים', 'צה״כ')}: <b>{d.z[k]}</b></span>)}
          </div>
        )}
        {ctx.expired && <div className="warn-line">נתוני הזמנים אינם זמינים לתאריך זה — נדרש חיבור לעדכון</div>}
      </div>
      {d && <SidePanel snap={snap} ctx={ctx} />}
    </div>
  )
}

// ---------------------------------------------------------------- zmanim
export function ZmanimScreen({ snap, ctx, screen }: ScreenProps) {
  const d = ctx.day!
  const showLearn = screen.config?.show_learning !== false && d.learn.length > 0
  const showAdd = screen.config?.show_additions !== false && d.add.length + d.rem.length > 0
  return (
    <div className="grid-zmanim">
      <Panel title="זמני היום" className="zm-main">
        <FitBox max={40} min={24} deps={[d]}><div className={snap.enabled_zmanim.filter(k => d.z[k]).length > 9 ? 'two-cols' : ''}><ZmanimList snap={snap} day={d} /></div></FitBox>
      </Panel>
      {(showLearn || showAdd) && (
        <div className="zm-side">
          {showLearn && <Panel title="לימוד יומי"><dl className="zlist small">{d.learn.map(l => <div key={l.key}><dt>{l.label}</dt><dd>{l.value}</dd></div>)}</dl></Panel>}
          {showAdd && <Panel title="פרטי היום"><FitBox max={34} min={22} className="add-box"><ul className="bullets">{[...d.add, ...d.rem].map((a, i) => <li key={i}>{a}</li>)}</ul></FitBox></Panel>}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- prayers & lessons
function PrayerTable({ items }: { items: Day['prayers'] }) {
  return (
    <FitBox max={44} min={24} deps={[items.length]}>
      <table className="ptable"><tbody>
        {items.map(p => <tr key={p.id}><th>{p.name}{(p.note || p.location) && <small> {p.note || p.location}</small>}</th><td>{p.time}</td></tr>)}
      </tbody></table>
    </FitBox>
  )
}
function LessonTable({ items }: { items: Day['lessons'] }) {
  return (
    <FitBox max={40} min={22} deps={[items.length]}>
      <table className="ptable lessons"><tbody>
        {items.map((l, i) => <tr key={l.id + i}><th>{l.title}{l.teacher && <small> {l.teacher}</small>}</th><td>{l.time}</td></tr>)}
      </tbody></table>
    </FitBox>
  )
}
export function PrayersScreen({ snap, ctx, screen }: ScreenProps) {
  const pr = prayersFor(snap, ctx.day, screen.id)
  const ls = lessonsFor(snap, ctx.day, screen.id)
  const showP = screen.type !== 'lessons' && pr.length > 0
  const showL = screen.type !== 'prayers' && ls.length > 0
  return (
    <div className={'grid-2' + (showP && showL ? '' : ' single')}>
      {showP && <Panel title={ctx.day?.flags.is_shabbat ? 'זמני תפילות — שבת קודש' : 'זמני תפילות היום'}><PrayerTable items={pr} /></Panel>}
      {showL && <Panel title="שיעורים היום"><LessonTable items={ls} /></Panel>}
    </div>
  )
}

// ---------------------------------------------------------------- announcements
export function AnnouncementsScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const items = announcementsFor(snap, ctx, screen.id)
  const per = Math.max(1, Math.min(3, screen.config?.per_page || 2))
  const pages = chunk(items, per)
  const i = usePager(pages.length, durationMs, screen.id)
  const page = pages[i] || []
  return (
    <div className={`ann-grid n${page.length}`}>
      {page.map(a => (
        <Panel key={a.id} title={a.title} className="ann">
          <div className={'ann-body' + (a.image_url ? ' with-img' : '')}>
            {a.image_url && <img src={a.image_url} alt="" className="ann-img" onError={e => (e.currentTarget.style.display = 'none')} />}
            <FitBox max={per === 1 ? 52 : 40} min={22} deps={[a.id]}><div className="rich" dangerouslySetInnerHTML={{ __html: a.body_html }} /></FitBox>
          </div>
        </Panel>
      ))}
      {pages.length > 1 && <div className="dots">{pages.map((_, k) => <span key={k} className={k === i ? 'on' : ''} />)}</div>}
    </div>
  )
}

// ---------------------------------------------------------------- halacha
export function HalachaScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const items = halachotFor(snap, ctx, screen.config?.selection_id)
  const i = usePager(items.length, durationMs, screen.id)
  const h = items[i]
  if (!h) return null
  return (
    <Panel className="halacha parchment">
      <h1 className="halacha-title">{h.title}</h1>
      <FitBox max={56} min={26} className="halacha-text" deps={[h.id]}><p>{h.text}</p></FitBox>
      <div className="attrib">
        {h.is_sample && <span className="sample">טקסט לדוגמה — אינו הלכה</span>}
        מקור: {h.source_title}{h.source_ref ? ` · ${h.source_ref}` : ''}{h.attribution && !h.is_sample ? ` · ${h.attribution}` : ''}
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------- memorials
export function MemorialsScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const style = screen.config?.style || screen.template_key || 'list'
  const { week, permanent } = memorialsFor(snap, ctx, screen.id, screen.config?.mode || 'both')
  const perPage = style === 'tree' ? 24 : style === 'cards' ? 6 : 10
  const pages = chunk(permanent, perPage)
  const i = usePager(Math.max(1, pages.length), durationMs, screen.id)
  const name = (m: any) => `${m.full_name}${m.parent_name ? ` ${m.ben} ${m.parent_name}` : ''} ${m.gender === 'f' ? 'ע״ה' : 'ז״ל'}`
  return (
    <div className="memorials">
      <div className="mem-head"><span className="candle" aria-hidden="true" /><h1>לעילוי נשמת</h1><span className="candle" aria-hidden="true" /></div>
      {week.length > 0 && (
        <Panel title="אזכרות השבוע" className="mem-week">
          <ul>{week.map(m => <li key={m.id + m.date}><b>{name(m)}</b><span>{m.hebrew_date.split(' ה')[0]}{m.days === 0 ? ' — היום' : m.days === 1 ? ' — מחר' : ` — ביום ${WEEKDAYS[new Date(m.date + 'T12:00:00Z').getUTCDay()]}`}</span></li>)}</ul>
        </Panel>
      )}
      {pages.length > 0 && (
        <div className={'mem-' + style}>
          {(pages[i] || []).map(m => (
            <div key={m.id} className="mem-item">
              {style !== 'list' && <span className="leaf" aria-hidden="true" />}
              <b>{name(m)}</b><small>נלב״ע {m.hebrew_date}</small>
            </div>
          ))}
        </div>
      )}
      <div className="mem-foot">ת.נ.צ.ב.ה</div>
    </div>
  )
}

// ---------------------------------------------------------------- sponsors & birthdays
export function SponsorsScreen({ snap, ctx, screen }: ScreenProps) {
  const list = sponsorsFor(snap, ctx, screen.id)
  const order = ['year', 'month', 'week', 'day']
  return (
    <div className="sponsors">
      {order.filter(p => list.some(s => s.period === p)).map(p => (
        <Panel key={p} title={periodLabel[p]} className="sponsor">
          {list.filter(s => s.period === p).map(s => (
            <div key={s.id} className="sp-item"><div className="sp-text">{dedicationText(s)}</div>{s.sponsor_name && <div className="sp-by">נדבת {s.sponsor_name}</div>}</div>
          ))}
        </Panel>
      ))}
    </div>
  )
}
export function BirthdaysScreen({ snap, ctx }: ScreenProps) {
  const list = birthdaysFor(snap, ctx)
  return (
    <Panel className="birthdays parchment">
      <h1 className="festive">מזל טוב!</h1>
      <p className="muted-line">יום הולדת שמח ל:</p>
      <ul>{list.map(b => <li key={b.id}><b>{b.name}</b>{b.message && <span>{b.message}</span>}</li>)}</ul>
    </Panel>
  )
}

// ---------------------------------------------------------------- hilula (two automatic layouts)
const imgStatus = new Map<string, 'ok' | 'error'>()
export function useImageStatus(url: string | null): 'none' | 'loading' | 'ok' | 'error' {
  const [s, setS] = useState<'none' | 'loading' | 'ok' | 'error'>(() => (!url ? 'none' : imgStatus.get(url) || 'loading'))
  useEffect(() => {
    if (!url) { setS('none'); return }
    const known = imgStatus.get(url)
    if (known) { setS(known); return }
    setS('loading')
    const img = new Image()
    let done = false
    const finish = (v: 'ok' | 'error') => { if (done) return; done = true; imgStatus.set(url, v); setS(v) }
    img.onload = () => finish(img.naturalWidth > 0 ? 'ok' : 'error')
    img.onerror = () => finish('error')
    const t = setTimeout(() => finish('error'), 4000) // not cached offline / too slow → text layout
    img.src = url
    return () => clearTimeout(t)
  }, [url])
  return s
}

export function HilulaView({ t, layout = 'auto', imagePercent = 38, upcoming, snap }: {
  t: Tzadik; layout?: 'auto' | 'image' | 'noimage'; imagePercent?: number; upcoming?: { id: string; hebrew: string; days: number }[]; snap?: Snapshot
}) {
  const status = useImageStatus(layout === 'noimage' ? null : t.image_url)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(0)
  useEffect(() => { setPages(1); setPage(0) }, [t])
  useEffect(() => {
    if (pages <= 1) return
    const id = setInterval(() => setPage(p => (p + 1) % pages), 12000)
    return () => clearInterval(id)
  }, [pages])
  if (status === 'loading') return <div className="hilula pending" /> // decide layout before painting → no flicker
  const withImage = status === 'ok' && layout !== 'noimage'
  const bioPages = splitPages(t.biography, pages)
  const name = [t.honorific, t.display_name].filter(Boolean).join(' ')
  const meta = [t.hilula_date_str && `יום ההילולה: ${t.hilula_date_str}`, t.death_year_str && `נפטר בשנת ${t.death_year_str}`, t.burial_place && `מקום קבורתו: ${t.burial_place}`].filter(Boolean).join(' | ')
  const body = (
    <>
      <section className="h-sec">
        <h2>תולדות חייו</h2>
        <FitBox max={withImage ? 38 : 42} min={24} className="h-bio" deps={[t, page, pages, withImage]}
          onOverflow={o => { if (o && pages < 4) setPages(pages + 1) }}>
          <p>{bioPages[page] || bioPages[0]}{pages > 1 && <span className="cont"> ({page + 1}/{pages})</span>}</p>
        </FitBox>
      </section>
      <section className="h-sec teaching">
        <h2>{t.teaching_title || 'מתורתו'}</h2>
        <FitBox max={withImage ? 36 : 40} min={22} className="h-teach" deps={[t, withImage]}><p>{t.teaching_text}</p></FitBox>
        {t.teaching_source && <cite>[{t.teaching_source}]</cite>}
      </section>
    </>
  )
  return (
    <div className={'hilula ' + (withImage ? 'with-image' : 'no-image') + (upcoming?.length ? ' has-side' : '')}>
      <div className="h-frame">
        <header className="h-header">
          <div className="eyebrow">הילולא דצדיקיא</div>
          <h1>{name}</h1>
          {meta && <div className="h-meta">{meta}</div>}
          <div className="rule" />
        </header>
        {withImage ? (
          <div className="h-main" style={{ gridTemplateColumns: `${imagePercent}% 1fr` }}>
            <figure className="portrait">
              <img src={t.image_url!} alt={t.image_alt || `תמונת ${name}`} />
              {t.image_attribution && <figcaption>{t.image_attribution}</figcaption>}
            </figure>
            <div className="h-content">{body}</div>
          </div>
        ) : <div className="h-main full">{body}</div>}
        <footer className="h-foot">זכות הצדיק תגן עלינו ועל כל ישראל, אמן</footer>
      </div>
      {upcoming && upcoming.length > 0 && snap && (
        <aside className="side h-side">
          <h3>ההילולות הקרובות</h3>
          <ul>{upcoming.slice(0, 7).map(u => <li key={u.id + u.hebrew}><b>{[snap.tzadikim[u.id]?.honorific, snap.tzadikim[u.id]?.display_name].filter(Boolean).join(' ')}</b><span>{u.days === 0 ? 'היום' : u.hebrew}</span></li>)}</ul>
        </aside>
      )}
    </div>
  )
}

export function HilulaScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const list = hilulotFor(snap, ctx)
  const i = usePager(list.length, durationMs, screen.id)
  const cur = list[i]
  const upcoming = useMemo(() => (logicalDay(snap, ctx)?.hil_up || []).filter(u => u.days > 0 || !list.some(l => l.id === u.id)), [ctx.day, ctx.afterDayChange, list])
  if (!cur) return null
  return <HilulaView t={cur.t} imagePercent={screen.config?.image_percent || 38} upcoming={screen.config?.show_upcoming === false ? [] : upcoming} snap={snap} />
}

// ---------------------------------------------------------------- shabbat
export function ShabbatScreen({ snap, ctx }: ScreenProps) {
  const { friDay, satDay } = shabbatDays(snap, ctx)
  const label = satDay?.holiday || friDay?.holiday_e
  const pr = [...(friDay?.prayers || []).filter(p => p.type !== 'shacharit').map(p => ({ ...p, when: 'ערב שבת' })), ...(satDay?.prayers || []).map(p => ({ ...p, when: 'שבת' }))]
  return (
    <div className="grid-2">
      <Panel title={`שבת קודש${satDay?.parsha ? ' — פרשת ' + satDay.parsha : ''}`} className="shabbat">
        {label && <div className="holiday-line">{label}</div>}
        <dl className="zlist big">
          {friDay?.z.candle_lighting && <div><dt>הדלקת נרות</dt><dd>{friDay.z.candle_lighting}</dd></div>}
          {friDay?.z.sunset && <div><dt>שקיעה</dt><dd>{friDay.z.sunset}</dd></div>}
          {satDay?.z.shma_mga && <div><dt>סוף זמן ק״ש מג״א</dt><dd>{satDay.z.shma_mga}</dd></div>}
          {satDay?.z.shma_gra && <div><dt>סוף זמן ק״ש גר״א</dt><dd>{satDay.z.shma_gra}</dd></div>}
          {satDay?.z.shabbat_end && <div><dt>צאת השבת</dt><dd>{satDay.z.shabbat_end}</dd></div>}
          {satDay?.z.shabbat_end_rt && <div><dt>רבנו תם</dt><dd>{satDay.z.shabbat_end_rt}</dd></div>}
        </dl>
      </Panel>
      <Panel title="תפילות השבת">
        {pr.length ? <FitBox max={40} min={22}><table className="ptable"><tbody>{pr.map((p, k) => <tr key={p.id + k}><th>{p.name}<small> {p.when}</small></th><td>{p.time}</td></tr>)}</tbody></table></FitBox>
          : <p className="muted-line">לא הוגדרו תפילות לשבת</p>}
      </Panel>
    </div>
  )
}

// ---------------------------------------------------------------- combined & content
export function CombinedScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const pr = prayersFor(snap, ctx.day, screen.id)
  const hal = halachotFor(snap, ctx, screen.config?.selection_id)
  const ann = announcementsFor(snap, ctx, screen.id)
  const ai = usePager(ann.length, durationMs, screen.id)
  return (
    <div className="combined">
      <Panel className="c-clock"><div className="c-time">{ctx.time}</div><div className="c-date">{ctx.hebrewLabel}</div>
        {ctx.day && <div className="c-z">{['sunrise', 'sunset', 'tzeit'].filter(k => ctx.day!.z[k]).map(k => <span key={k}>{snap.zmanim_labels[k]} <b>{ctx.day!.z[k]}</b></span>)}</div>}</Panel>
      <Panel title="תפילות היום" className="c-prayers">{pr.length ? <PrayerTable items={pr} /> : <p className="muted-line">אין תפילות להיום</p>}</Panel>
      <Panel title={hal[0]?.title || 'הלכה יומית'} className="c-halacha">{hal[0] ? <FitBox max={34} min={20}><p>{hal[0].text}</p></FitBox> : <p className="muted-line">—</p>}</Panel>
      <Panel title={ann[ai]?.title || 'הודעות'} className="c-ann">{ann[ai] ? <FitBox max={32} min={20} deps={[ai]}><div className="rich" dangerouslySetInnerHTML={{ __html: ann[ai].body_html }} /></FitBox> : <p className="muted-line">אין הודעות</p>}</Panel>
    </div>
  )
}
export function ContentScreen({ snap, ctx, screen, durationMs }: ScreenProps) {
  const items = contentFor(snap, ctx, screen.id)
  const i = usePager(items.length, durationMs, screen.id)
  const c = items[i]
  if (!c) return null
  return (
    <Panel className="halacha parchment">
      <h1 className="halacha-title">{c.title}</h1>
      <FitBox max={50} min={24} className="halacha-text" deps={[c.id]}><p>{c.body}</p></FitBox>
      {c.source && <div className="attrib">מקור: {c.source}</div>}
    </Panel>
  )
}

export const SCREENS: Record<string, (p: ScreenProps) => React.ReactElement | null> = {
  clock: ClockScreen, zmanim: ZmanimScreen, prayers: PrayersScreen, lessons: PrayersScreen, prayers_lessons: PrayersScreen,
  announcements: AnnouncementsScreen, halacha: HalachaScreen, memorials: MemorialsScreen, sponsors: SponsorsScreen,
  birthdays: BirthdaysScreen, hilula: HilulaScreen, shabbat: ShabbatScreen, combined: CombinedScreen, content: ContentScreen,
}

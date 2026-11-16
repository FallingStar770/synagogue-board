// Pure display logic (no React) — unit tested in logic.test.ts.
export type HebInfo = { day: number; month: number; year: number; day_str: string; month_name: string; year_str: string; str: string }
export type Day = {
  h: HebInfo; he: HebInfo; parsha: string | null; holiday: string | null; holiday_e: string | null
  flags: { weekday: number; is_shabbat: boolean; is_yom_tov: boolean; assur_today: boolean; assur_tomorrow: boolean; is_rosh_chodesh: boolean; is_fast: boolean; is_chanukah: boolean; is_chol_hamoed: boolean; is_erev_shabbat: boolean }
  z: Record<string, string>; zi: Record<string, string>; add: string[]; rem: string[]; learn: { key: string; label: string; value: string }[]
  prayers: { id: string; type: string; type_name: string; name: string; time: string; description?: string | null; location?: string | null; note?: string | null }[]
  lessons: { id: string; title: string; teacher?: string | null; location?: string | null; time: string; duration?: number | null; note?: string | null }[]
  hil: string[]; hil_e: string[]; hil_up: { id: string; date: string; days: number; hebrew: string }[]
  mem: string[]; mem_e: string[]; mem_week: { id: string; date: string; days: number }[]
  bday: string[]; bday_e: string[]; halacha: Record<string, string[]>
}
export type ScreenDef = {
  id: string; name: string; type: string; enabled?: boolean; template_key: string; duration_seconds: number; config: Record<string, any>
  conditions: { days_of_week?: number[]; shabbat_mode?: 'any' | 'only' | 'hide'; time_from?: string | null; time_to?: string | null; date_from?: string | null; date_to?: string | null }
  fallback: 'skip' | 'message'; fallback_text: string | null
}
export type Tzadik = { display_name: string; honorific: string | null; biography: string; teaching_title: string | null; teaching_text: string; teaching_source: string | null; image_url: string | null; image_alt: string | null; image_attribution: string | null; burial_place: string | null; death_year_str: string | null; hilula_date_str: string }
export type Snapshot = {
  schema: 1; local_date: string; engine: string
  settings: { name: string; address: string | null; city: string | null; logo_url: string | null; timezone: string; day_change: 'sunset' | 'midnight'; footer_text: string | null; theme: Record<string, any>; nusach: string; in_israel: boolean }
  zmanim_labels: Record<string, string>; enabled_zmanim: string[]
  screens: ScreenDef[]; links: Record<string, Record<string, string[]>>
  announcements: { id: string; title: string; body_html: string; image_url: string | null; start_at: string | null; end_at: string | null; priority: number; hide_on_shabbat: boolean; screens: string[] }[]
  halachot: Record<string, { title: string; text: string; source_ref: string | null; source_title: string; author: string | null; attribution: string | null; license: string; is_sample: boolean }>
  halacha_selections: { id: string; name: string }[]
  memorials: Record<string, { full_name: string; parent_name: string | null; ben: string; gender: string; hebrew_date: string; permanent: boolean; screens: string[] }>
  sponsorships: { id: string; sponsor_name: string | null; dedication_type: string; honoree_name: string | null; text: string | null; period: string; start: string; end: string; footer: boolean; screens: string[] }[]
  birthdays: Record<string, { name: string; message: string | null }>
  tzadikim: Record<string, Tzadik>
  content: { id: string; kind: string; title: string; body: string; source: string | null; start: string | null; end: string | null; screens: string[] }[]
  media: string[]; days: Record<string, Day>
}

export const WEEKDAYS = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']

export function localParts(now: Date, tz: string) {
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat('en-GB', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(now)
  } catch {
    parts = new Intl.DateTimeFormat('en-GB', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(now)
  }
  const g = (t: string) => parts.find(p => p.type === t)?.value || '00'
  const date = `${g('year')}-${g('month')}-${g('day')}`
  const hh = g('hour'), mm = g('minute'), ss = g('second')
  const weekday = new Date(date + 'T12:00:00Z').getUTCDay()
  return { date, hh, mm, ss, weekday, minutes: +hh * 60 + +mm }
}

export const addDays = (date: string, n: number) => {
  const d = new Date(date + 'T12:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export type Ctx = {
  now: Date; date: string; time: string; seconds: string; weekday: number; minutes: number
  day: Day | null; afterDayChange: boolean; hebrewLabel: string; holiday: string | null; inShabbat: boolean; expired: boolean
}

export function dayContext(snap: Snapshot, now: Date): Ctx {
  const p = localParts(now, snap.settings.timezone)
  const day = snap.days[p.date] || null
  let after = false
  if (day && snap.settings.day_change === 'sunset' && day.zi.sunset) after = now >= new Date(day.zi.sunset)
  let hebrewLabel = ''
  let inShabbat = false
  if (day) {
    const h = after ? day.he : day.h
    const wd = after ? (p.weekday + 1) % 7 : p.weekday
    hebrewLabel = `${after ? 'ליל' : 'יום'} ${WEEKDAYS[wd]} - ${h.day_str} ${h.month_name} ה${h.year_str}`
    const f = day.flags
    const end = day.zi.shabbat_end ? new Date(day.zi.shabbat_end) : day.zi.tzeit ? new Date(day.zi.tzeit) : null
    const start = day.zi.candle_lighting ? new Date(day.zi.candle_lighting) : day.zi.sunset ? new Date(day.zi.sunset) : null
    const inToday = f.assur_today && (f.assur_tomorrow || !end || now < end)
    const startsTonight = f.assur_tomorrow && !!start && now >= start
    inShabbat = inToday || startsTonight
  }
  return {
    now, date: p.date, time: `${p.hh}:${p.mm}`, seconds: p.ss, weekday: p.weekday, minutes: p.minutes, day,
    afterDayChange: after, hebrewLabel, holiday: day ? (after ? day.holiday_e : day.holiday) : null, inShabbat, expired: !day,
  }
}

const toMin = (s: string) => { const [h, m] = s.split(':').map(Number); return h * 60 + m }

export function screenAllowed(s: ScreenDef, ctx: Ctx): boolean {
  const c = s.conditions || {}
  if (c.days_of_week?.length && !c.days_of_week.includes(ctx.weekday)) return false
  if (c.shabbat_mode === 'only' && !ctx.inShabbat) return false
  if (c.shabbat_mode === 'hide' && ctx.inShabbat) return false
  if (c.date_from && ctx.date < c.date_from) return false
  if (c.date_to && ctx.date > c.date_to) return false
  if (c.time_from || c.time_to) {
    const from = c.time_from ? toMin(c.time_from) : 0
    const to = c.time_to ? toMin(c.time_to) : 24 * 60
    const m = ctx.minutes
    const inside = from <= to ? m >= from && m < to : m >= from || m < to // supports overnight windows
    if (!inside) return false
  }
  return true
}

const linked = (screens: string[] | undefined, id: string) => !screens || screens.length === 0 || screens.includes(id)

// ---------------------------------------------------------------- content selectors
export function announcementsFor(snap: Snapshot, ctx: Ctx, screenId: string) {
  return snap.announcements.filter(a =>
    (!a.start_at || new Date(a.start_at) <= ctx.now) && (!a.end_at || new Date(a.end_at) > ctx.now) &&
    !(a.hide_on_shabbat && ctx.inShabbat) && linked(a.screens, screenId))
}
export function prayersFor(snap: Snapshot, day: Day | null, screenId: string) {
  return (day?.prayers || []).filter(p => linked(snap.links?.prayer?.[p.id], screenId))
}
export function lessonsFor(snap: Snapshot, day: Day | null, screenId: string) {
  return (day?.lessons || []).filter(l => linked(snap.links?.lesson?.[l.id], screenId))
}
export function hilulotFor(snap: Snapshot, ctx: Ctx): { id: string; t: Tzadik }[] {
  const ids = ctx.day ? (ctx.afterDayChange ? ctx.day.hil_e : ctx.day.hil) : []
  return ids.filter(id => snap.tzadikim[id]).map(id => ({ id, t: snap.tzadikim[id] }))
}
export function halachotFor(snap: Snapshot, ctx: Ctx, selectionId?: string | null) {
  if (!ctx.day) return []
  const sel = selectionId && ctx.day.halacha[selectionId] ? selectionId : snap.halacha_selections[0]?.id
  return (sel ? ctx.day.halacha[sel] || [] : []).filter(id => snap.halachot[id]).map(id => ({ id, ...snap.halachot[id] }))
}
/** Lists computed per civil day that must follow the Hebrew day (switch after sunset). */
export function logicalDay(snap: Snapshot, ctx: Ctx): Day | null {
  return ctx.afterDayChange ? snap.days[addDays(ctx.date, 1)] || ctx.day : ctx.day
}
export function memorialsFor(snap: Snapshot, ctx: Ctx, screenId: string, mode: string) {
  const week = (logicalDay(snap, ctx)?.mem_week || []).filter(m => snap.memorials[m.id] && linked(snap.memorials[m.id].screens, screenId))
    .map(m => ({ id: m.id, ...snap.memorials[m.id], days: m.days, date: m.date }))
  const permanent = Object.entries(snap.memorials).filter(([, m]) => m.permanent && linked(m.screens, screenId))
    .map(([id, m]) => ({ id, ...m, days: null as number | null, date: null as string | null }))
  return { week: mode === 'permanent' ? [] : week, permanent: mode === 'week' ? [] : permanent }
}
export function sponsorsFor(snap: Snapshot, ctx: Ctx, screenId?: string) {
  return snap.sponsorships.filter(s => s.start <= ctx.date && ctx.date <= s.end && (!screenId || linked(s.screens, screenId)))
}
export function birthdaysFor(snap: Snapshot, ctx: Ctx) {
  const ids = ctx.day ? (ctx.afterDayChange ? ctx.day.bday_e : ctx.day.bday) : []
  return ids.filter(id => snap.birthdays[id]).map(id => ({ id, ...snap.birthdays[id] }))
}
export function contentFor(snap: Snapshot, ctx: Ctx, screenId: string) {
  return snap.content.filter(c => (!c.start || c.start <= ctx.date) && (!c.end || ctx.date <= c.end) && linked(c.screens, screenId))
}
export function shabbatDays(snap: Snapshot, ctx: Ctx) {
  const wd = ctx.weekday
  const fri = wd === 6 ? addDays(ctx.date, -1) : addDays(ctx.date, 5 - wd)
  const sat = addDays(fri, 1)
  return { fri, sat, friDay: snap.days[fri] || null, satDay: snap.days[sat] || null }
}

export function hasContent(snap: Snapshot, ctx: Ctx, s: ScreenDef): boolean {
  switch (s.type) {
    case 'clock': return true
    case 'zmanim': return !!ctx.day
    case 'prayers': return prayersFor(snap, ctx.day, s.id).length > 0
    case 'lessons': return lessonsFor(snap, ctx.day, s.id).length > 0
    case 'prayers_lessons': return prayersFor(snap, ctx.day, s.id).length + lessonsFor(snap, ctx.day, s.id).length > 0
    case 'announcements': return announcementsFor(snap, ctx, s.id).length > 0
    case 'halacha': return halachotFor(snap, ctx, s.config?.selection_id).length > 0
    case 'memorials': { const m = memorialsFor(snap, ctx, s.id, s.config?.mode || 'both'); return m.week.length + m.permanent.length > 0 }
    case 'sponsors': return sponsorsFor(snap, ctx, s.id).length > 0
    case 'birthdays': return birthdaysFor(snap, ctx).length > 0
    case 'hilula': return hilulotFor(snap, ctx).length > 0
    case 'shabbat': { const d = shabbatDays(snap, ctx); return !!(d.friDay || d.satDay) }
    case 'combined': return !!ctx.day
    case 'content': return contentFor(snap, ctx, s.id).length > 0
    default: return false
  }
}

export type PlaylistItem = { screen: ScreenDef; fallback: boolean }

/** Screens to rotate right now: enabled (snapshot contains only enabled ones), allowed by their
 * conditions, and either with content or with a configured fallback message. */
export function playlist(snap: Snapshot, ctx: Ctx): PlaylistItem[] {
  const out: PlaylistItem[] = []
  for (const s of snap.screens) {
    if (s.enabled === false) continue
    if (!screenAllowed(s, ctx)) continue
    if (ctx.expired && s.type !== 'clock') continue // no calendar data → never show invented data
    if (hasContent(snap, ctx, s)) out.push({ screen: s, fallback: false })
    else if (s.fallback === 'message' && s.fallback_text) out.push({ screen: s, fallback: true })
  }
  return out
}

export function dedicationText(s: Snapshot['sponsorships'][number]): string {
  const prefix: Record<string, string> = { iluy_nishmat: 'לעילוי נשמת', refua: 'לרפואת', hatzlacha: 'להצלחת', nidvat: 'נדבת', zivug: 'לזיווג הגון', custom: '' }
  return [prefix[s.dedication_type] || '', s.honoree_name, s.text].filter(Boolean).join(' ')
}
export const periodLabel: Record<string, string> = { day: 'פרנס היום', week: 'פרנס השבוע', month: 'פרנס החודש', year: 'פרנס השנה' }

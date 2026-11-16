import { describe, expect, it } from 'vitest'
import { createHash } from 'node:crypto'
import { addDays, announcementsFor, dayContext, hilulotFor, playlist, screenAllowed, type Day, type ScreenDef, type Snapshot } from './logic'
import { splitPages } from './fit'
import { sha256Text } from './sha256'
import { validateSnapshot } from './store'

const heb = (d: number, m = 'כסלו') => ({ day: d, month: 9, year: 5787, day_str: `${d}`, month_name: m, year_str: 'תשפ״ז', str: `${d} ${m}` })
function day(date: string, over: Partial<Day> = {}, flags: Partial<Day['flags']> = {}): Day {
  const wd = new Date(date + 'T12:00:00Z').getUTCDay()
  return {
    h: heb(5), he: heb(6), parsha: 'ויצא', holiday: null, holiday_e: null,
    flags: { weekday: wd, is_shabbat: wd === 6, is_yom_tov: false, assur_today: wd === 6, assur_tomorrow: wd === 5, is_rosh_chodesh: false, is_fast: false, is_chanukah: false, is_chol_hamoed: false, is_erev_shabbat: wd === 5, ...flags },
    z: { sunrise: '06:08', sunset: '16:39' },
    zi: { sunset: `${date}T16:39:00+02:00`, tzeit: `${date}T17:18:00+02:00`, ...(wd === 5 ? { candle_lighting: `${date}T16:19:00+02:00` } : {}), ...(wd === 6 ? { shabbat_end: `${date}T17:18:00+02:00` } : {}) },
    add: [], rem: [], learn: [], prayers: [], lessons: [], hil: [], hil_e: [], hil_up: [], mem: [], mem_e: [], mem_week: [], bday: [], bday_e: [], halacha: {},
    ...over,
  }
}
const screen = (id: string, type: string, conditions: ScreenDef['conditions'] = {}, extra: Partial<ScreenDef> = {}): ScreenDef =>
  ({ id, name: id, type, template_key: 'default', duration_seconds: 10, config: {}, conditions, fallback: 'skip', fallback_text: null, ...extra })

function snap(days: Record<string, Day>, over: Partial<Snapshot> = {}): Snapshot {
  return {
    schema: 1, local_date: Object.keys(days)[0], engine: 'test',
    settings: { name: 'בית הכנסת', address: null, city: null, logo_url: null, timezone: 'Asia/Jerusalem', day_change: 'sunset', footer_text: null, theme: {}, nusach: 'sefardi', in_israel: true },
    zmanim_labels: { sunrise: 'זריחה', sunset: 'שקיעה' }, enabled_zmanim: ['sunrise', 'sunset'], screens: [], links: {}, announcements: [], halachot: {},
    halacha_selections: [], memorials: {}, sponsorships: [], birthdays: {}, tzadikim: {}, content: [], media: [], days, ...over,
  }
}

describe('day context', () => {
  it('switches to the next Hebrew day after sunset (ליל)', () => {
    const s = snap({ '2026-11-15': day('2026-11-15') })
    const before = dayContext(s, new Date('2026-11-15T14:00:00Z')) // 16:00 local
    const after = dayContext(s, new Date('2026-11-15T15:00:00Z')) // 17:00 local
    expect(before.afterDayChange).toBe(false)
    expect(before.hebrewLabel).toContain('יום ראשון')
    expect(after.afterDayChange).toBe(true)
    expect(after.hebrewLabel).toContain('ליל שני')
    expect(after.hebrewLabel).toContain('6 כסלו')
  })
  it('midnight day-change never switches early', () => {
    const s = snap({ '2026-11-15': day('2026-11-15') })
    s.settings.day_change = 'midnight'
    expect(dayContext(s, new Date('2026-11-15T20:00:00Z')).afterDayChange).toBe(false)
  })
  it('detects the Shabbat window from candle lighting to havdala', () => {
    const s = snap({ '2026-11-20': day('2026-11-20'), '2026-11-21': day('2026-11-21') })
    expect(dayContext(s, new Date('2026-11-20T13:00:00Z')).inShabbat).toBe(false) // Fri 15:00
    expect(dayContext(s, new Date('2026-11-20T14:30:00Z')).inShabbat).toBe(true) // Fri 16:30 after candles
    expect(dayContext(s, new Date('2026-11-21T10:00:00Z')).inShabbat).toBe(true)
    expect(dayContext(s, new Date('2026-11-21T15:30:00Z')).inShabbat).toBe(false) // Sat 17:30 after havdala
  })
  it('marks dates beyond the cached range as expired (no invented data)', () => {
    const s = snap({ '2026-11-15': day('2026-11-15') })
    const c = dayContext(s, new Date('2028-01-01T10:00:00Z'))
    expect(c.expired).toBe(true)
    s.screens = [screen('c', 'clock'), screen('z', 'zmanim')]
    expect(playlist(s, c).map(p => p.screen.id)).toEqual(['c'])
  })
})

describe('playlist', () => {
  const base = snap({ '2026-11-15': day('2026-11-15', { prayers: [{ id: 'p1', type: 'shacharit', type_name: 'שחרית', name: 'שחרית', time: '06:30' }] }) })
  const now = new Date('2026-11-15T08:00:00Z') // Sunday 10:00
  it('respects order, conditions and skips empty screens', () => {
    base.screens = [screen('a', 'clock'), screen('b', 'announcements'), screen('c', 'prayers'), screen('d', 'clock', { days_of_week: [5, 6] }), screen('e', 'hilula')]
    expect(playlist(base, dayContext(base, now)).map(p => p.screen.id)).toEqual(['a', 'c'])
  })
  it('shows a configured fallback message instead of skipping', () => {
    base.screens = [screen('b', 'announcements', {}, { fallback: 'message', fallback_text: 'אין הודעות' })]
    expect(playlist(base, dayContext(base, now))[0].fallback).toBe(true)
  })
  it('time windows including overnight', () => {
    const ctx = dayContext(base, now)
    expect(screenAllowed(screen('x', 'clock', { time_from: '09:00', time_to: '11:00' }), ctx)).toBe(true)
    expect(screenAllowed(screen('x', 'clock', { time_from: '11:00', time_to: '12:00' }), ctx)).toBe(false)
    expect(screenAllowed(screen('x', 'clock', { time_from: '22:00', time_to: '11:00' }), ctx)).toBe(true)
    expect(screenAllowed(screen('x', 'clock', { shabbat_mode: 'only' }), ctx)).toBe(false)
  })
})

describe('content filters', () => {
  it('announcements expire on the device clock and hide on Shabbat', () => {
    const s = snap({ '2026-11-21': day('2026-11-21') }, {
      announcements: [
        { id: '1', title: 'a', body_html: '', image_url: null, start_at: null, end_at: '2026-11-21T09:00:00Z', priority: 0, hide_on_shabbat: false, screens: [] },
        { id: '2', title: 'b', body_html: '', image_url: null, start_at: null, end_at: null, priority: 0, hide_on_shabbat: true, screens: [] },
        { id: '3', title: 'c', body_html: '', image_url: null, start_at: null, end_at: null, priority: 0, hide_on_shabbat: false, screens: ['other'] },
        { id: '4', title: 'd', body_html: '', image_url: null, start_at: null, end_at: null, priority: 0, hide_on_shabbat: false, screens: ['me'] },
      ],
    })
    const ctx = dayContext(s, new Date('2026-11-21T10:00:00Z'))
    expect(announcementsFor(s, ctx, 'me').map(a => a.id)).toEqual(['4'])
  })
  it('hilula uses the evening list after sunset', () => {
    const t = { display_name: 'צדיק', honorific: null, biography: 'x', teaching_title: null, teaching_text: 'y', teaching_source: null, image_url: null, image_alt: null, image_attribution: null, burial_place: null, death_year_str: null, hilula_date_str: '' }
    const s = snap({ '2026-11-15': day('2026-11-15', { hil: ['a'], hil_e: ['b'] }) }, { tzadikim: { a: t, b: { ...t, display_name: 'ב' } } })
    expect(hilulotFor(s, dayContext(s, new Date('2026-11-15T10:00:00Z')))[0].id).toBe('a')
    expect(hilulotFor(s, dayContext(s, new Date('2026-11-15T16:00:00Z')))[0].id).toBe('b')
  })
})

describe('integrity & utils', () => {
  it('sha256 matches node crypto (Hebrew + large input)', () => {
    for (const s of ['', 'abc', 'שלום עולם — בדיקה', 'x'.repeat(100000) + 'ש']) {
      expect(sha256Text(s)).toBe(createHash('sha256').update(s, 'utf8').digest('hex'))
    }
  })
  it('validates snapshot shape', () => {
    expect(validateSnapshot(snap({ '2026-11-15': day('2026-11-15') }))).toBe(true)
    expect(validateSnapshot({ schema: 2 })).toBeFalsy()
  })
  it('splits long text into pages without losing words', () => {
    const text = 'משפט ראשון. משפט שני ארוך יותר. משפט שלישי! משפט רביעי? משפט חמישי.'
    const pages = splitPages(text, 3)
    expect(pages.length).toBe(3)
    expect(pages.join(' ').replace(/\s+/g, ' ')).toBe(text)
  })
  it('addDays across month', () => { expect(addDays('2026-11-30', 1)).toBe('2026-12-01') })
})

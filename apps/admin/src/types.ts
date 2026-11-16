export type Screen = {
  id: string; name: string; type: string; template_key: string; enabled: boolean; sort_order: number
  duration_seconds: number; config: Record<string, any>
  conditions: { days_of_week: number[]; shabbat_mode: 'any' | 'only' | 'hide'; time_from?: string | null; time_to?: string | null; date_from?: string | null; date_to?: string | null }
  fallback: 'skip' | 'message'; fallback_text: string | null
}
export type Option = { key: string; label: string }
export type Rule = {
  day_kind: string; days_of_week: number[]; replaces_regular: boolean; time_mode: 'fixed' | 'relative'
  fixed_time: string | null; relative_zman: string | null; offset_minutes: number; rounding: string
  duration_minutes: number | null; valid_from: string | null; valid_to: string | null
}
export const emptyRule = (): Rule => ({
  day_kind: 'daily', days_of_week: [], replaces_regular: false, time_mode: 'fixed', fixed_time: '07:00',
  relative_zman: null, offset_minutes: 0, rounding: 'none', duration_minutes: null, valid_from: null, valid_to: null,
})
export const WEEKDAYS = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'ש׳']
export const HEB_MONTHS: Option[] = [
  ['7', 'תשרי'], ['8', 'חשון'], ['9', 'כסלו'], ['10', 'טבת'], ['11', 'שבט'], ['12', 'אדר / אדר א׳'], ['13', 'אדר ב׳'],
  ['1', 'ניסן'], ['2', 'אייר'], ['3', 'סיון'], ['4', 'תמוז'], ['5', 'אב'], ['6', 'אלול'],
].map(([key, label]) => ({ key, label }))
export const LEAP_POLICIES: Option[] = [
  { key: 'adar_ii', label: 'בשנה מעוברת: באדר ב׳' }, { key: 'adar_i', label: 'בשנה מעוברת: באדר א׳' },
  { key: 'both', label: 'בשנה מעוברת: בשני האדרים' },
]
const HEB_DAYS = ['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט', 'י', 'יא', 'יב', 'יג', 'יד', 'טו', 'טז', 'יז', 'יח', 'יט', 'כ', 'כא', 'כב', 'כג', 'כד', 'כה', 'כו', 'כז', 'כח', 'כט', 'ל']
export const hebDay = (n: number) => { const s = HEB_DAYS[n - 1] || String(n); return s.length === 1 ? s + '׳' : s.slice(0, -1) + '״' + s.slice(-1) }

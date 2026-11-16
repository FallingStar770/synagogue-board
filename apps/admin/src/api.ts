// Thin fetch wrapper: same-origin cookies, CSRF header on state-changing requests, Hebrew errors.
let csrfToken = ''
export const setCsrf = (t: string) => { csrfToken = t }

export class ApiError extends Error {
  status: number
  details: unknown
  constructor(status: number, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.details = details
  }
}

type Opts = { method?: string; body?: unknown; form?: FormData; raw?: boolean }

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const method = opts.method || (opts.body || opts.form ? 'POST' : 'GET')
  const headers: Record<string, string> = {}
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch('/api/v1' + path, {
      method, headers, credentials: 'same-origin',
      body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'אין חיבור לשרת. בדקו את חיבור האינטרנט.')
  }
  if (res.status === 401 && !path.startsWith('/auth/')) {
    window.dispatchEvent(new Event('auth:expired'))
  }
  if (!res.ok) {
    let msg = `שגיאה ${res.status}`
    let details: unknown
    try {
      const j = await res.json()
      msg = j?.error?.message || j?.detail || msg
      details = j?.error?.details
    } catch { /* not json */ }
    throw new ApiError(res.status, msg, details)
  }
  if (opts.raw) return res as unknown as T
  if (res.status === 204) return null as T
  return res.json()
}

export const get = <T = any>(p: string) => api<T>(p)
export const post = <T = any>(p: string, body?: unknown) => api<T>(p, { method: 'POST', body: body ?? {} })
export const patch = <T = any>(p: string, body: unknown) => api<T>(p, { method: 'PATCH', body })
export const put = <T = any>(p: string, body: unknown) => api<T>(p, { method: 'PUT', body })
export const del = (p: string) => api(p, { method: 'DELETE' })

export async function upload(file: File, meta: Record<string, string> = {}) {
  const f = new FormData()
  f.append('file', file)
  Object.entries(meta).forEach(([k, v]) => v && f.append(k, v))
  return api('/media', { form: f })
}

export async function download(path: string, filename: string) {
  const res = await api<Response>(path, { raw: true })
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}

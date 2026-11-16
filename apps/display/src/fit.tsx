import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

/** Shrinks the font size (within readable limits) until the content fits its box.
 * Reports `overflow` when even the minimum size does not fit, so the caller can paginate
 * instead of silently cutting text. */
export function FitBox({ children, max, min, className = '', deps = [], onOverflow }: {
  children: ReactNode; max: number; min: number; className?: string; deps?: unknown[]; onOverflow?: (o: boolean) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState(max)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    let lo = min, hi = max, best = min
    el.style.fontSize = max + 'px'
    if (el.scrollHeight <= el.clientHeight + 1) { setSize(max); onOverflow?.(false); return }
    while (hi - lo > 0.5) { // binary search for the largest size that fits
      const mid = (lo + hi) / 2
      el.style.fontSize = mid + 'px'
      if (el.scrollHeight <= el.clientHeight + 1) { best = mid; lo = mid } else hi = mid
    }
    el.style.fontSize = best + 'px'
    setSize(best)
    onOverflow?.(el.scrollHeight > el.clientHeight + 1)
  }, [max, min, ...deps])
  return <div ref={ref} className={'fitbox ' + className} style={{ fontSize: size }}>{children}</div>
}

/** Split long text into n roughly equal pages on sentence boundaries. */
export function splitPages(text: string, pages: number): string[] {
  if (pages <= 1) return [text]
  const sentences = text.match(/[^.!?׃:]+[.!?׃:]*\s*/g) || [text]
  const target = text.length / pages
  const out: string[] = []
  let cur = ''
  for (const s of sentences) {
    if (cur && (cur + s).length > target && out.length < pages - 1) { out.push(cur.trim()); cur = '' }
    cur += s
  }
  if (cur.trim()) out.push(cur.trim())
  return out
}

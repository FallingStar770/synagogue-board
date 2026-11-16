import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { get } from '../api'
import { Btn, Card, PageHeader, Select } from '../ui'

export function TvFrame({ src, title }: { src: string; title: string }) {
  return (
    <div className="tv-frame"><div className="tv-inner"><iframe title={title} src={src} /></div></div>
  )
}

export default function DisplayPreview() {
  const { data: screens = [] } = useQuery<any[]>({ queryKey: ['screens'], queryFn: () => get('/screens') })
  const [screen, setScreen] = useState('')
  const [key, setKey] = useState(0)
  const src = `../display/?preview=1${screen ? '&screen=' + screen : ''}&k=${key}`
  return (
    <div>
      <PageHeader title="תצוגה מקדימה" subtitle="כך נראה הלוח בטלוויזיה (1920×1080). התצוגה מתעדכנת אוטומטית לאחר שמירת שינויים."
        actions={<>
          <Btn icon="refresh" onClick={() => setKey(k => k + 1)}>רענון</Btn>
          <a className="btn primary" href={src} target="_blank" rel="noopener">פתיחה במסך מלא</a>
        </>} />
      <Card>
        <div className="toolbar">
          <label>הצגת מסך:&nbsp;
            <Select value={screen} onChange={setScreen} placeholder="כל המסכים ברצף (Playlist)"
              options={screens.map(s => ({ key: s.id, label: s.name + (s.enabled ? '' : ' (כבוי)') }))} />
          </label>
        </div>
        <TvFrame src={src} title="תצוגה מקדימה" />
      </Card>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { get } from '../api'
import { useAuth } from '../main'
import { Badge, Card, Icon, Loading, PageHeader, fmtDateTime } from '../ui'

export default function Dashboard() {
  const { me } = useAuth()
  const z = useQuery({ queryKey: ['zmanim-today'], queryFn: () => get('/zmanim') })
  const screens = useQuery({ queryKey: ['screens'], queryFn: () => get('/screens') })
  const ann = useQuery({ queryKey: ['announcements', 'active'], queryFn: () => get('/announcements?active_only=true&limit=5') })
  const hil = useQuery({ queryKey: ['hilulot-active'], queryFn: () => get('/hilulot/active') })
  const status = useQuery({ queryKey: ['status'], queryFn: () => get('/maintenance/status'), enabled: me.role === 'admin', refetchInterval: 30000 })
  const prayers = useQuery({ queryKey: ['prayers-day', z.data?.date], queryFn: () => get('/prayers/day?date=' + z.data.date), enabled: !!z.data })
  return (
    <div>
      <PageHeader title={`שלום ${me.display_name || me.username}`} subtitle={z.data ? <>{z.data.hebrew_date}{z.data.parsha && <> · פרשת {z.data.parsha}</>}{z.data.holiday && <> · {z.data.holiday}</>}</> : ' '} />
      <div className="dash-grid">
        <Card title="מסכים פעילים" actions={<Link to="/screens" className="link">ניהול</Link>}>
          {screens.isLoading ? <Loading /> : (
            <ul className="mini-list">
              {screens.data?.map((s: any) => <li key={s.id}><span className={'dot ' + (s.enabled ? 'on' : 'off')} />{s.name}<span className="muted">{s.duration_seconds} שנ׳</span></li>)}
            </ul>
          )}
        </Card>
        <Card title="זמני היום" actions={<Link to="/zmanim" className="link">הגדרות</Link>}>
          {z.isLoading ? <Loading /> : (
            <dl className="kv">
              {z.data?.zmanim.filter((x: any) => x.enabled).slice(0, 10).map((x: any) => <div key={x.key}><dt>{x.label}</dt><dd>{x.time}</dd></div>)}
            </dl>
          )}
        </Card>
        <Card title="תפילות היום" actions={<Link to="/prayers" className="link">ניהול</Link>}>
          {prayers.data?.items?.length ? (
            <dl className="kv">{prayers.data.items.map((p: any) => <div key={p.id}><dt>{p.name}</dt><dd>{p.time}</dd></div>)}</dl>
          ) : <p className="muted">אין תפילות מוגדרות להיום</p>}
        </Card>
        <Card title="הודעות פעילות" actions={<Link to="/announcements" className="link">ניהול</Link>}>
          {ann.data?.items?.length ? <ul className="mini-list">{ann.data.items.map((a: any) => <li key={a.id}>{a.title}</li>)}</ul> : <p className="muted">אין הודעות פעילות</p>}
        </Card>
        <Card title="הילולה היום" actions={<Link to="/hilulot" className="link">ניהול</Link>}>
          {hil.data?.items?.length ? <ul className="mini-list">{hil.data.items.map((t: any) => <li key={t.id}><Icon name="star" size={16} />{[t.honorific, t.display_name].filter(Boolean).join(' ')}</li>)}</ul> : <p className="muted">אין הילולה היום</p>}
        </Card>
        {me.role === 'admin' && (
          <Card title="מצב מסכי הטלוויזיה" actions={<Link to="/devices" className="link">ניהול</Link>}>
            {status.data?.devices?.length ? (
              <ul className="mini-list">
                {status.data.devices.map((d: any) => <li key={d.name}>
                  <span className={'dot ' + (d.online ? 'on' : 'off')} />{d.name}
                  {d.revoked ? <Badge tone="off">בוטל</Badge> : <span className="muted">{d.last_seen_at ? fmtDateTime(d.last_seen_at) : 'טרם התחבר'}</span>}
                </li>)}
              </ul>
            ) : <p className="muted">עדיין לא צומדו מסכים. <Link to="/devices">צימוד מסך</Link></p>}
            {status.data?.snapshot && <small className="muted">גרסת נתונים לתצוגה: {status.data.snapshot.version}</small>}
          </Card>
        )}
      </div>
    </div>
  )
}

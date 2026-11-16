import '@fontsource/heebo/400.css'
import '@fontsource/heebo/500.css'
import '@fontsource/heebo/700.css'
import '@fontsource/heebo/800.css'
import '@fontsource/frank-ruhl-libre/500.css'
import '@fontsource/frank-ruhl-libre/700.css'
import './styles.css'
import { createRoot } from 'react-dom/client'
import App from './App'

if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('./sw.js', { scope: './' })
      setInterval(() => { if (navigator.onLine) reg.update().catch(() => {}) }, 60 * 60 * 1000)
      let reloaded = false
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        // a new app version took over: reload once so the TV runs the matching code
        if (!reloaded && navigator.serviceWorker.controller && sessionStorage.getItem('sw-ready')) { reloaded = true; location.reload() }
        sessionStorage.setItem('sw-ready', '1')
      })
      if (navigator.serviceWorker.controller) sessionStorage.setItem('sw-ready', '1')
    } catch { /* SW needs https or localhost; the app still runs, only refresh-without-network is limited */ }
  })
}

createRoot(document.getElementById('root')!).render(<App />)

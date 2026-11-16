import { createHash } from 'node:crypto'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Emits precache-manifest.json listing every built file so the service worker can cache the
// whole app on first load and start again with no network (offline-first TV).
function precacheManifest(): Plugin {
  return {
    name: 'precache-manifest',
    generateBundle(_, bundle) {
      const files = Object.keys(bundle).filter(f => !f.endsWith('.map'))
      const all = ['./', './index.html', ...files.map(f => './' + f)]
      const version = createHash('sha256').update(files.sort().join('|')).digest('hex').slice(0, 12)
      this.emitFile({ type: 'asset', fileName: 'precache-manifest.json', source: JSON.stringify({ version, files: all }) })
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), precacheManifest()],
  server: { port: 5174, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist', assetsInlineLimit: 0 },
  test: { environment: 'node' },
} as any)

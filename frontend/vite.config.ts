import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv, type Plugin } from 'vite'

function cspPlugin(apiBase: string | undefined): Plugin {
  let origin = ''
  if (apiBase) {
    try {
      origin = new URL(apiBase).origin
    } catch {
      origin = ''
    }
  }
  const connect = origin && origin !== 'null' ? `'self' ${origin}` : "'self'"
  const csp = [
    "default-src 'self'",
    "base-uri 'none'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src ${connect}`,
    "manifest-src 'self'",
    "media-src 'none'",
    "worker-src 'none'",
  ].join('; ')
  return {
    name: 'sk-under-csp',
    transformIndexHtml(html) {
      return html.replace(
        '</head>',
        `    <meta http-equiv="Content-Security-Policy" content="${csp}" />\n  </head>`,
      )
    },
  }
}

export default defineConfig(({ mode }) => {
  const envDir = fileURLToPath(new URL('..', import.meta.url))
  const env = loadEnv(mode, envDir, '')
  const apiBase = env.VITE_API_BASE_URL?.trim() || process.env.VITE_API_BASE_URL?.trim()
  return {
    plugins: [react(), tailwindcss(), cspPlugin(apiBase)],
    envDir,
    server: { port: 5173, host: '127.0.0.1' },
  }
})

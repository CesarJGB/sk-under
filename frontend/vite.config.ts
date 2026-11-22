import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  envDir: mode === 'development' ? fileURLToPath(new URL('..', import.meta.url)) : undefined,
  server: { port: 5173, host: '127.0.0.1' },
}))

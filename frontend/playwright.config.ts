import { defineConfig } from '@playwright/test'

const baseURL = 'http://127.0.0.1:14733'

export default defineConfig({
  testDir: './tests',
  use: { baseURL, browserName: 'chromium' },
  webServer: {
    command: 'npm run dev -- --port 14733',
    env: { VITE_API_BASE_URL: baseURL },
    url: baseURL,
  },
})

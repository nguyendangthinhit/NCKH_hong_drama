import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api được chuyển tới backend FastAPI local (serving/post_analyzer/backend, cổng 8020)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8020' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:8020' } },
})

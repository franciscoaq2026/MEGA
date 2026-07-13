import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Encaminha as chamadas /api para o backend FastAPI em desenvolvimento
      '/api': 'http://localhost:8000',
    },
  },
})

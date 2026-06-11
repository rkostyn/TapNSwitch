import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const API_TARGET = process.env.API_TARGET ?? 'http://localhost:8001'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      '/auth':   { target: API_TARGET, changeOrigin: true },
      '/event':  { target: API_TARGET, changeOrigin: true },
      '/match':  { target: API_TARGET, changeOrigin: true },
      '/round':  { target: API_TARGET, changeOrigin: true },
      '/throw':  { target: API_TARGET, changeOrigin: true },
      '/player': { target: API_TARGET, changeOrigin: true },
    },
  },
})

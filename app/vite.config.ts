import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // API_TARGET for the dev-server proxy, from the shell or .env.development
  // (loadEnv, since Vite only exposes VITE_ values to the client by itself).
  const env = loadEnv(mode, process.cwd(), '')
  const API_TARGET = env.API_TARGET || 'http://localhost:8001'

  return {
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
        '/lanes':  { target: API_TARGET, changeOrigin: true },
        '/venue':  { target: API_TARGET, changeOrigin: true },
        '/tv':     { target: API_TARGET, changeOrigin: true },
        '/integrations': { target: API_TARGET, changeOrigin: true },
      },
    },
  }
})

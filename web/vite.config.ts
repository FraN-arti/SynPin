import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

const backendPort = process.env.BACKEND_PORT || '2088'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  server: {
    host: '0.0.0.0',
    port: 2099,
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', () => {}) // Suppress errors during backend restart
        },
      },
      '/ws': {
        target: `ws://localhost:${backendPort}`,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', () => {}) // Suppress ECONNABORTED during backend restart
        },
      },
    },
  },
})

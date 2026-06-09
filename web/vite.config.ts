import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

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
        target: 'http://localhost:2088',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:2088',
        ws: true,
      },
    },
  },
})

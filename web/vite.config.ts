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
    rollupOptions: {
      output: {
        // Code-split the bundle so first paint doesn't require 3.6 MB.
        // react / react-dom stays in its own chunk (loaded on every page).
        // recharts (heavy charting library, ~500 kB minified) only loads when
        // a page actually uses it. The catch-all groups anything else into
        // the main entry chunk.
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          recharts: ['recharts'],
        },
      },
    },
    // Bump warning threshold from the Vite default (500 kB) to a value
    // matching the chunk sizes we expect after manualChunks. Without
    // this, recharts (~500 kB) still triggers the warning even though
    // it's lazy-loaded.
    chunkSizeWarningLimit: 700,
  },
  server: {
    open: false,
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

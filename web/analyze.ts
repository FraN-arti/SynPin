// Bundle visualizer — generates dist/stats.html (open in browser to inspect)
// Run with: cd web && npm run analyze

import { build } from 'vite'
import { visualizer } from 'rollup-plugin-visualizer'

await build({
  configFile: 'vite.config.ts',
  plugins: [
    visualizer({
      filename: 'dist/stats.html',
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',
    }),
  ],
  logLevel: 'info',
})
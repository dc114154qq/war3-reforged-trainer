import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Multi-file build loaded by pywebview from frontend/dist. The style guide has its own
// config (vite.styleguide.config.ts) and never ships in the app.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    // Match the launcher's WebView2 version check; do not let a Vite upgrade raise it silently.
    target: 'chrome111',
    cssTarget: 'chrome111',
    emptyOutDir: true,
    rollupOptions: {
      input: 'index.html',
    },
  },
})

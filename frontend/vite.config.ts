import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    allowedHosts: true, // Allow all hosts (tunneling)
    hmr: {
      clientPort: 443, // Force client to use HTTPS port (Tunnel) instead of 5174
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true, // Enable WebSockets properly
      },
    }
  }
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true,
    host: true, // Listen on all addresses
    allowedHosts: ['all'], // Allow all hosts for tunneling
    // hmr: {
    //   clientPort: 443, // DISABLED: Only for specific tunnel setups
    // },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true, // Enable WebSockets properly
      },
    }
  }
})

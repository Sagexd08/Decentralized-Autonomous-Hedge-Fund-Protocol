<<<<<<< HEAD
import path from 'node:path'
=======
>>>>>>> D!
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
<<<<<<< HEAD
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
=======
>>>>>>> D!
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
  },
})

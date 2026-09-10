import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Фронт ходит к API через прокси, чтобы в коде не было ни адресов, ни CORS:
    // адрес бэкенда — забота окружения, а не компонентов.
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});

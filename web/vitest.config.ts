import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

/**
 * Конфиг тестов отдельным файлом: в vitest 5 секция `test` живёт здесь, а не
 * в `vite.config.ts` — попытка положить её туда не проходит типизацию.
 *
 * `jsdom`, а не браузерный прогон: DoD Ф6 требует тестов на формы и таблицы, и
 * поднимать браузер ради «виден ли пункт меню» значит менять секунды на минуты.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});

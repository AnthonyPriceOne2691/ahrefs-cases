import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { ApiError } from './api/client';
import { App } from './App';
import { glassTheme } from './theme';

import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import './styles/glass.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Прогон идёт часами, а метрики за закрытые месяцы не меняются —
      // агрессивная инвалидация здесь только дёргает бэкенд.
      staleTime: 30_000,
      // Повтор имеет смысл там, где второй заход может ответить иначе. На
      // протухшем токене он не может: сервер ответит тем же `401`. Живьём это
      // выглядело как мигание белым — каждый повтор снимал карточку и ставил
      // заглушку загрузки заново (найдено 15.09.2026 вместе с самим протуханием).
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.needsLogin) && failureCount < 1,
    },
  },
});

const root = document.getElementById('root');
if (!root) throw new Error('#root не найден: index.html разошёлся с main.tsx');

createRoot(root).render(
  <StrictMode>
    <MantineProvider theme={glassTheme} defaultColorScheme="auto">
      <QueryClientProvider client={queryClient}>
        <Notifications position="top-right" />
        <App />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);

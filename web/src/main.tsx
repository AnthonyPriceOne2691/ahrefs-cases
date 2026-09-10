import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

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
      retry: 1,
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

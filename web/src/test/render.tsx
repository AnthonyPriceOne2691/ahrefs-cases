/**
 * Рендер с провайдерами, без которых компоненты не живут.
 *
 * Их два, и оба стоят в `main.tsx`: Mantine и React Query. Экран, ходящий в
 * API, без клиента запросов падает на первом же `useQuery` — а падает он в
 * чужом тесте, который просто рендерит приложение целиком.
 *
 * Клиент свой на каждый рендер и без повторов: общий кэш переживал бы тест, а
 * повтор запроса прячет отказ, который тест и проверяет.
 */
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';

import { glassTheme } from '../theme';

export function renderApp(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MantineProvider theme={glassTheme}>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </MantineProvider>,
  );
}

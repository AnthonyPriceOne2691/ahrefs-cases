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
import { BrowserRouter } from 'react-router-dom';

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

/**
 * Рендер **экрана**, живущего внутри маршрутизации приложения.
 *
 * Помощников два, и это повторяет настоящее дерево: `main.tsx` даёт Mantine и
 * React Query, а маршрутизатор живёт внутри `App`. Добавить его в `renderApp`
 * нельзя — тест, рендерящий `App` целиком, получил бы два вложенных
 * маршрутизатора, а это ошибка react-router.
 *
 * `BrowserRouter`, а не `MemoryRouter`: экран меняет адрес (строка таблицы
 * ведёт на карточку), и проверять это честнее по `window.location`, как увидит
 * человек.
 */
export function renderScreen(ui: ReactElement) {
  return renderApp(<BrowserRouter>{ui}</BrowserRouter>);
}

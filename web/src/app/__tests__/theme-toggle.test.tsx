/**
 * Переключатель темы внизу бокового меню.
 *
 * Проверяется через `Shell`, а не через сам компонент: половина требования —
 * это МЕСТО (левая колонка, отдельно от разделов), и тест на компонент в
 * вакууме его не увидел бы.
 *
 * Кнопка ищется по роли и подписи, а не по разметке: подпись — это и есть
 * доступность, обещанная задачей, и разъехаться с ней тест не даст.
 *
 * Провайдер здесь свой, с `defaultColorScheme`: именно он включает у Mantine
 * хранение выбора (`localStorage`), и без него «переживает ли перезагрузку»
 * проверять не на чем. Хранилище чистится между тестами — выбор по условию
 * задачи переживает перезагрузку, а значит пережил бы и соседний тест.
 */
import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { glassTheme } from '../../theme';
import { Shell } from '../Shell';

/** Ключ хранения Mantine. Он же и есть «переживает перезагрузку». */
const STORED = 'mantine-color-scheme-value';

const ME = {
  email: 'clerk@test.local',
  full_name: 'Сотрудник',
  group: 'user',
  rights: ['read'],
};

beforeEach(() => {
  localStorage.removeItem(STORED);
  document.documentElement.removeAttribute('data-mantine-color-scheme');
  rememberToken('токен');
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(ME), { status: 200 })),
  );
});

afterEach(() => {
  forgetToken();
  localStorage.removeItem(STORED);
  vi.unstubAllGlobals();
});

/** Рендер оболочки целиком — как в `main.tsx`, вместе с хранением темы. */
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider theme={glassTheme} defaultColorScheme="auto">
      <QueryClientProvider client={client}>
        <AuthProvider>
          <BrowserRouter>
            <Shell>
              <div>содержимое</div>
            </Shell>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

/** Кнопка в любом из двух состояний: подпись обещает, КУДА переключит. */
function toggle() {
  return screen.getByRole('button', { name: /светлая тема|тёмная тема/ });
}

describe('переключатель темы', () => {
  it('стоит внизу левой колонки, а не среди разделов', async () => {
    show();
    await screen.findByRole('link', { name: 'Проекты' });

    const button = toggle();
    const navbar = document.querySelector('nav');
    expect(navbar).not.toBeNull();
    // В левой колонке — и при этом НЕ внутри списка разделов: он не раздел, и
    // читаться в одном ряду с ними не должен.
    expect(navbar).toContainElement(button);
    const sections = screen.getByRole('link', { name: 'Проекты' }).parentElement;
    expect(sections).not.toBeNull();
    expect(within(sections as HTMLElement).queryByRole('button')).toBeNull();
  });

  it('по клику тема меняется, и значок показывает новую', async () => {
    // jsdom отвечает «система светлая» (заглушка `matchMedia`), поэтому
    // действующая тема на старте светлая, а значок предлагает тёмную.
    show();
    await screen.findByRole('link', { name: 'Проекты' });
    expect(toggle()).toHaveAccessibleName('тёмная тема');

    await userEvent.click(toggle());

    await waitFor(() =>
      expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark'),
    );
    // Значок перевернулся: теперь он предлагает вернуться в светлую.
    expect(toggle()).toHaveAccessibleName('светлая тема');
  });

  it('выбор переживает перезагрузку страницы', async () => {
    const first = show();
    await screen.findByRole('link', { name: 'Проекты' });

    await userEvent.click(toggle());
    await waitFor(() => expect(localStorage.getItem(STORED)).toBe('dark'));

    // Перезагрузка страницы: дерево снимается целиком и собирается заново —
    // в память между рендерами ничего не переносится, остаётся только
    // хранилище браузера.
    first.unmount();
    document.documentElement.removeAttribute('data-mantine-color-scheme');
    show();

    await screen.findByRole('link', { name: 'Проекты' });
    expect(toggle()).toHaveAccessibleName('светлая тема');
    expect(document.documentElement).toHaveAttribute('data-mantine-color-scheme', 'dark');
  });
});

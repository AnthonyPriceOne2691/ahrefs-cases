/**
 * Экран проектов. Примеры приёмки E1–E10.
 *
 * Главное, что здесь проверяется поведением: «данных не хватает» не сливается
 * с «плохим», а фильтры уходят **на сервер** — иначе таблица соврёт на второй
 * странице.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderScreen } from '../../test/render';
import { ProjectsPage } from '../ProjectsPage';

interface Reply {
  status: number;
  body: unknown;
}

function project(id: number, domain: string, group: string | null, score: number | null) {
  return {
    id,
    domain,
    niche: 'финтех',
    geo: 'US',
    service_type: 'seo',
    period_start: '2025-01-01',
    period_end: '2025-12-01',
    publishable: true,
    status: 'classified',
    group,
    score,
  };
}

const ROWS = [
  project(1, 'good.example', 'good', 1400),
  project(2, 'poor.example', 'poor', 120),
  project(3, 'thin.example', 'insufficient_data', null),
  project(4, 'fresh.example', null, null),
];

/** Ответы по пути; последний запрос запоминается, чтобы проверить параметры. */
function server(reply: Reply): { urls: string[] } {
  const urls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      urls.push(url);
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return { urls };
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
  // Адрес живёт в jsdom дольше теста: без сброса следующий тест начинается на
  // карточке, куда увёл предыдущий.
  window.history.pushState({}, '', '/');
});

describe('экран проектов: таблица', () => {
  it('E1 и E2: группы показаны словами, непроклассифицированный — честно', async () => {
    rememberToken('токен');
    server({ status: 200, body: ROWS });

    renderScreen(<ProjectsPage />);

    expect(await screen.findByText('good.example')).toBeInTheDocument();
    expect(screen.getByText('хороший')).toBeInTheDocument();
    expect(screen.getByText('плохой')).toBeInTheDocument();
    // Пустая ячейка читалась бы как ошибка загрузки, а это законное состояние.
    expect(screen.getByText('не классифицирован')).toBeInTheDocument();
    // Счёт округляется: дробные знаки читались бы как точность, которой нет.
    expect(screen.getByText('1 400')).toBeInTheDocument();
  });

  it('E3: «данных не хватает» — не «плохой»', async () => {
    rememberToken('токен');
    server({ status: 200, body: ROWS });

    renderScreen(<ProjectsPage />);
    // Ждём строку таблицы, а не подпись: «данных не хватает» написано и на
    // чипе фильтра, и поиск по тексту поймал бы его ещё до ответа сервера.
    await screen.findByText('thin.example');

    const groups = [...document.querySelectorAll('[data-group]')].map((node) =>
      node.getAttribute('data-group'),
    );

    // Разными остаются и слово, и цвет: у них разные действия человека —
    // докупить историю против «кейса не будет».
    expect(groups).toContain('insufficient_data');
    expect(groups).toContain('poor');
    expect(screen.getByText('плохой')).toBeInTheDocument();
  });

  it('E10: клик по строке ведёт на карточку', async () => {
    rememberToken('токен');
    server({ status: 200, body: ROWS });

    renderScreen(<ProjectsPage />);
    await userEvent.click(await screen.findByText('good.example'));

    await waitFor(() => expect(window.location.pathname).toBe('/projects/1'));
  });
});

describe('экран проектов: фильтры и страницы', () => {
  it('E4: фильтр по группе уходит на сервер', async () => {
    rememberToken('токен');
    const { urls } = server({ status: 200, body: ROWS });

    renderScreen(<ProjectsPage />);
    await screen.findByText('good.example');
    await userEvent.click(screen.getByText('хорошие'));

    await waitFor(() => expect(urls.some((url) => url.includes('group=good'))).toBe(true));
  });

  it('E5: поиск по домену уходит на сервер', async () => {
    rememberToken('токен');
    const { urls } = server({ status: 200, body: ROWS });

    renderScreen(<ProjectsPage />);
    await screen.findByText('good.example');
    await userEvent.type(screen.getByLabelText('Поиск по домену'), 'good');

    await waitFor(() => expect(urls.some((url) => url.includes('query=good'))).toBe(true));
  });

  it('E9: полная страница даёт листание, первая страница — без «назад»', async () => {
    rememberToken('токен');
    const full = Array.from({ length: 50 }, (_, index) =>
      project(index + 1, `p${index}.example`, 'good', 100),
    );
    const { urls } = server({ status: 200, body: full });

    renderScreen(<ProjectsPage />);
    await screen.findByText('p0.example');

    expect(screen.getByRole('button', { name: 'Назад' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Вперёд' }));

    expect(await screen.findByText('Страница 2')).toBeInTheDocument();
    await waitFor(() => expect(urls.some((url) => url.includes('offset=50'))).toBe(true));
  });
});

describe('экран проектов: пусто и отказ', () => {
  it('E7: пусто вообще — предлагает загрузить список', async () => {
    rememberToken('токен');
    server({ status: 200, body: [] });

    renderScreen(<ProjectsPage />);

    expect(await screen.findByText(/Загрузите список/)).toBeInTheDocument();
  });

  it('E6: пусто по фильтру — предлагает снять фильтр, а не грузить список', async () => {
    rememberToken('токен');
    server({ status: 200, body: [] });

    renderScreen(<ProjectsPage />);
    await screen.findByText(/Загрузите список/);
    await userEvent.type(screen.getByLabelText('Поиск по домену'), 'нетакого');

    expect(await screen.findByText(/Снимите фильтр/)).toBeInTheDocument();
  });

  it('E8: отказ показан текстом сервера', async () => {
    rememberToken('токен');
    server({ status: 403, body: { detail: 'нет права read: группа user' } });

    renderScreen(<ProjectsPage />);

    expect(await screen.findByText(/нет права read/)).toBeInTheDocument();
  });
});

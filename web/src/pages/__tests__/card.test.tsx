/**
 * Карточка проекта. Примеры приёмки E1–E10.
 *
 * Проверяется не разметка, а то, ради чего экран существует: по нему должно
 * быть видно, **почему** группа именно такая, и числа обязаны совпадать с
 * вердиктом, а не считаться заново.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderScreen } from '../../test/render';
import { ProjectCardPage } from '../ProjectCardPage';

const PROJECT = {
  id: 7,
  domain: 'klinika.example',
  niche: 'медицина',
  geo: 'RU',
  service_type: 'seo',
  period_start: '2024-03-01',
  period_end: '2025-09-01',
  publishable: true,
  status: 'classified',
  group: 'good',
  score: 1400.4,
};

const VERDICT = {
  group: 'good',
  score: 1400.4,
  ruleset_version: '0.0.0-default',
  decided_at: '2026-09-11T10:00:00Z',
  reasons: [
    {
      subject: 'org_traffic',
      fact: 140,
      threshold: 50,
      passed: true,
      decisive: true,
      note: 'рост выше порога',
    },
    {
      subject: 'refdomains',
      fact: 12,
      threshold: 30,
      passed: false,
      decisive: false,
      note: '',
    },
  ],
  point_a: { org_traffic: 1000 },
  point_b: { org_traffic: 2400 },
  comparison: [
    {
      subject: 'org_traffic',
      label: 'органический трафик',
      before: 1000,
      after: 2400,
      absolute: 1400,
      pct: 140,
    },
    {
      subject: 'kw_top10',
      label: 'ключи в топ-10',
      before: 0,
      after: 25,
      absolute: 25,
      pct: null,
    },
  ],
};

const CHARTS = [
  { title: 'Динамика органического трафика', svg: '<svg data-test="traffic"></svg>' },
  { title: 'Динамика позиций', svg: '<svg data-test="positions"></svg>' },
];

/** Карточка читает номер проекта из адреса, поэтому рендерится маршрутом — так
 *  же, как в приложении. Без маршрута `useParams` пуст, и экран честно висит на
 *  «загружаем», а тест списывает это на медленный сервер. */
function renderCard() {
  return renderScreen(
    <Routes>
      <Route path="/projects/:projectId" element={<ProjectCardPage />} />
    </Routes>,
  );
}

/** Обычная карточка с вердиктом и графиками — заготовка почти для всех примеров.
 *  Повторять её в каждом тесте значит править восемь мест, когда изменится форма
 *  ответа. */
function cardServer(overrides: Record<string, { status: number; body: unknown }> = {}) {
  server({
    '/api/projects/7': { status: 200, body: { project: PROJECT, verdict: VERDICT, series: [] } },
    '/api/projects/7/charts': { status: 200, body: CHARTS },
    ...overrides,
  });
}

function server(routes: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      // Сравниваем путь без параметров: у графиков появился `?grouping=…`, и
      // сопоставление целого адреса перестало находить маршрут.
      const path = url.split('?')[0] ?? url;
      const found = Object.entries(routes).find(([route]) => path.endsWith(route));
      const reply = found?.[1] ?? { status: 404, body: { detail: 'проекта 7 нет' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
}

beforeEach(() => {
  rememberToken('токен');
  window.history.pushState({}, '', '/projects/7');
});

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
  window.history.pushState({}, '', '/');
});

describe('карточка проекта: основание вердикта', () => {
  it('E1: шапка называет проект, группу, счёт и версию порогов', async () => {
    cardServer();

    renderCard();

    expect(await screen.findByText('klinika.example')).toBeInTheDocument();
    expect(screen.getByText('хороший')).toBeInTheDocument();
    // Счёт округляется, версия порогов стоит рядом: вердикт принадлежит версии,
    // и число без неё ничего не значит.
    expect(screen.getByText('счёт 1 400')).toBeInTheDocument();
    expect(screen.getByText('пороги 0.0.0-default')).toBeInTheDocument();
  });

  it('E2 и E10: таблица А → Б показывает числа вердикта', async () => {
    cardServer();

    renderCard();
    const row = await screen.findByText('органический трафик');

    const cells = [...(row.closest('tr')?.querySelectorAll('td') ?? [])].map((cell) =>
      // Разделитель разрядов у `toLocaleString('ru-RU')` — **неразрывный**
      // пробел: сравнение с обычным расходится невидимо глазу.
      cell.textContent?.replace(/\u00A0/g, ' '),
    );
    expect(cells).toEqual(['органический трафик', '1 000', '2 400', '+140 %']);
  });

  it('рост от нулевой базы не превращается в проценты', async () => {
    cardServer();

    renderCard();
    await screen.findByText('ключи в топ-10');

    // Сервер присылает `null`: рост с нуля формально бесконечен и по сути
    // ничего не значит. Подменить его «100 %» значило бы соврать.
    expect(screen.getByText('с нуля')).toBeInTheDocument();
  });

  it('E3: условия вердикта показаны с фактом, порогом и решающим', async () => {
    cardServer();

    renderCard();
    await screen.findByText('Почему эта группа');

    expect(screen.getByText('решающее')).toBeInTheDocument();
    expect(screen.getByText('прошло')).toBeInTheDocument();
    expect(screen.getByText('не прошло')).toBeInTheDocument();
  });

  it('E4: графики приходят готовыми и вставляются как есть', async () => {
    cardServer();

    renderCard();
    await screen.findByText('Динамика позиций');

    expect(document.querySelector('[data-test="traffic"]')).not.toBeNull();
    expect(document.querySelector('[data-test="positions"]')).not.toBeNull();
  });
});

it('E8 и E9: тумблер перерисовывает кривые и не трогает вердикт', async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      urls.push(url);
      const body = url.includes('/charts')
        ? [
            {
              title: 'Динамика органического трафика',
              svg: `<svg data-step="${url.split('grouping=')[1]}"></svg>`,
            },
          ]
        : { project: PROJECT, verdict: VERDICT, series: [] };
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );

  renderCard();
  await screen.findByText('Динамика органического трафика');
  await userEvent.click(screen.getByText('квартал'));

  await waitFor(() => expect(document.querySelector('[data-step="quarter"]')).not.toBeNull());
  // Вердикт принадлежит записи, а не виду экрана: таблица и условия те же.
  expect(screen.getByText('органический трафик')).toBeInTheDocument();
  expect(urls.filter((url) => url.includes('/api/projects/7?')).length).toBe(0);
});

describe('карточка проекта: состояния', () => {
  it('E5: без вердикта — что делать дальше, а не пустота', async () => {
    cardServer({
      '/api/projects/7': {
        status: 200,
        body: { project: { ...PROJECT, group: null, score: null }, verdict: null, series: [] },
      },
    });

    renderCard();

    expect(await screen.findByText(/Запустите классификацию/)).toBeInTheDocument();
  });

  it('E6: без рядов — карточка есть, кривых нет', async () => {
    cardServer({ '/api/projects/7/charts': { status: 200, body: [] } });

    renderCard();

    expect(await screen.findByText(/Кривых нет/)).toBeInTheDocument();
    expect(screen.getByText('klinika.example')).toBeInTheDocument();
  });

  it('E7: несуществующий проект назван словами', async () => {
    server({});

    renderCard();

    expect(await screen.findByText('проекта 7 нет')).toBeInTheDocument();
  });

  it('E8: отказ показан текстом сервера', async () => {
    server({
      '/api/projects/7': { status: 403, body: { detail: 'нет права read: группа user' } },
    });

    renderCard();

    expect(await screen.findByText(/нет права read/)).toBeInTheDocument();
  });

  it('E9: ссылка ведёт обратно к списку', async () => {
    cardServer();

    renderCard();
    await userEvent.click(await screen.findByText('← к списку проектов'));

    expect(window.location.pathname).toBe('/projects');
  });
});

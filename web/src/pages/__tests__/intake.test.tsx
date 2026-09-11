/**
 * Экран загрузки. Примеры приёмки E3–E12.
 *
 * Проверяется поведение, а не разметка: что человек видит после приёма, что
 * ему говорят при отказе и — главное — что кнопка запуска недоступна, когда
 * смета этого не позволяет. Цена ошибки здесь units заказчика, а не неудобство.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { IntakePage } from '../IntakePage';

interface Reply {
  status: number;
  body: unknown;
}

const OK_ESTIMATE = {
  projects: 10,
  units_estimated: 1980,
  requests_planned: 10,
  requests_cached: 2,
  scheme_lines: ['organic-traffic-history: историей, 10 проектов, 1980 units'],
  quota_left: 9500,
  quota_reserved: 0,
  verdict: 'ok',
  may_start: true,
  reason: '',
};

const REPORT = {
  origin: 'список.xlsx',
  accepted: 10,
  created: 10,
  updated: 0,
  rejected_rows: 0,
  by_reason: {},
  rejections: [],
  notices: [],
};

/** Ответы по пути запроса. Очередь на путь — чтобы второй запрос той же сметы
 *  мог ответить иначе: ровно это и значит «смета пересчиталась». */
function server(routes: Record<string, Reply | Reply[]>): { calls: string[] } {
  const calls: string[] = [];
  const queues = { ...routes };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = typeof input === 'string' ? input : input.toString();
      calls.push(path);
      const found = Object.entries(queues).find(([prefix]) => path.startsWith(prefix));
      if (!found) return new Response(JSON.stringify({ detail: 'нет пути' }), { status: 404 });
      const value = found[1];
      const reply = Array.isArray(value) ? (value.length > 1 ? value.shift() : value[0]) : value;
      return new Response(JSON.stringify(reply?.body), { status: reply?.status ?? 200 });
    }),
  );
  return { calls };
}

async function upload(file = new File(['x'], 'список.xlsx')) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  // `applyAccept: false`: подсказка `accept` фильтрует список в диалоге, но не
  // запрещает выбрать «все файлы» — отказ сервера по формату достижим, и
  // именно его проверяет E5.
  await userEvent.upload(input, file, { applyAccept: false });
  await userEvent.click(screen.getByRole('button', { name: 'Загрузить файл' }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('экран загрузки', () => {
  it('E3: принятый файл показан числами, а не «готово»', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': { status: 200, body: REPORT },
    });

    renderApp(<IntakePage />);
    await upload();

    expect(await screen.findByText('принято 10')).toBeInTheDocument();
    expect(screen.getByText('создано 10')).toBeInTheDocument();
    expect(screen.getByText('обновлено 0')).toBeInTheDocument();
  });

  it('E4: отклонённые строки названы номером и причиной', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 200,
        body: {
          ...REPORT,
          accepted: 9,
          created: 9,
          rejected_rows: 1,
          by_reason: { bad_date: 1 },
          rejections: [{ row_no: 12, field: 'period_start', reason: 'bad_date', detail: '31.02' }],
          notices: [],
        },
      },
    });

    renderApp(<IntakePage />);
    await upload();

    // Номер строки — тот, который человек ищет глазами в Excel.
    expect(await screen.findByText('12')).toBeInTheDocument();
    expect(screen.getByText('дата не разобрана')).toBeInTheDocument();
  });

  it('E9: принятые с замечаниями показаны отдельно от отклонённых', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 200,
        body: {
          ...REPORT,
          notices: [
            { row_no: 2, field: 'work_volume', reason: 'bad_number', detail: '214 ссылок' },
          ],
        },
      },
    });

    renderApp(<IntakePage />);
    await upload();

    // Проект принят: отклонённых строк нет, а непонятая ячейка названа.
    expect(await screen.findByText('принято 10')).toBeInTheDocument();
    expect(screen.queryByText(/отклонено строк/)).not.toBeInTheDocument();
    expect(screen.getByText('Принято с замечаниями')).toBeInTheDocument();
    expect(screen.getByText('214 ссылок')).toBeInTheDocument();
    expect(screen.getByText('с замечаниями 1')).toBeInTheDocument();
  });
});

describe('экран загрузки: отказы источника', () => {
  it('E5: отказ по формату показывается текстом сервера', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/file': {
        status: 400,
        body: { detail: 'не понимаю формат файла: отчёт.pdf. Ожидаю .xlsx или .csv' },
      },
    });

    renderApp(<IntakePage />);
    await upload(new File(['x'], 'отчёт.pdf'));

    expect(await screen.findByText(/не понимаю формат файла/)).toBeInTheDocument();
  });

  it('E6 и E7: ссылка на закрытую таблицу объясняет, что чинить', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/intake/link': {
        status: 400,
        body: { detail: 'таблица недоступна по ссылке: откройте доступ «по ссылке»' },
      },
    });

    renderApp(<IntakePage />);
    await userEvent.type(
      screen.getByLabelText(/Ссылка на Google Sheet/),
      'https://docs.google.com/spreadsheets/d/abc/edit',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Загрузить по ссылке' }));

    expect(await screen.findByText(/таблица недоступна по ссылке/)).toBeInTheDocument();
  });
});

describe('экран загрузки: смета и запуск', () => {
  it('E8: смета видна числами и разбивкой', async () => {
    rememberToken('токен');
    server({ '/api/runs/estimate': { status: 200, body: OK_ESTIMATE } });

    renderApp(<IntakePage />);

    expect(await screen.findByText('units по смете 1980')).toBeInTheDocument();
    expect(screen.getByText(/Остаток квоты: 9\s?500/)).toBeInTheDocument();
    expect(screen.getByText(/organic-traffic-history/)).toBeInTheDocument();
  });

  it('E9: не хватает квоты — кнопка недоступна, причина видна', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': {
        status: 200,
        body: {
          ...OK_ESTIMATE,
          quota_left: 300,
          verdict: 'not_enough',
          may_start: false,
          reason: 'не хватает units: остаток 300, нужно 1980, неснижаемый запас 500',
        },
      },
    });

    renderApp(<IntakePage />);

    expect(await screen.findByText(/не хватает units: остаток 300/)).toBeInTheDocument();
    expect(screen.getByTestId('start-run')).toBeDisabled();
  });

  it('E10: «остаток неизвестен» — своя причина, а не «мало квоты»', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': {
        status: 200,
        body: {
          ...OK_ESTIMATE,
          quota_left: null,
          verdict: 'unknown',
          may_start: false,
          reason: 'остаток квоты Ahrefs неизвестен. Прогон не начат: «не знаем» значит «не тратим»',
        },
      },
    });

    renderApp(<IntakePage />);

    expect(await screen.findByText(/остаток квоты Ahrefs неизвестен/)).toBeInTheDocument();
    expect(screen.getByText('Остаток квоты: неизвестен')).toBeInTheDocument();
    expect(screen.getByTestId('start-run')).toBeDisabled();
  });
});

describe('экран загрузки: прогон', () => {
  it('E11: запуск показывает номер прогона и его состояние', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/runs/7': {
        status: 200,
        body: {
          id: 7,
          status: 'done',
          projects_total: 10,
          projects_ok: 10,
          projects_failed: 0,
          units_estimated: 1980,
          units_actual: 1975,
          error: '',
        },
      },
      '/api/runs': { status: 202, body: { run_id: 7, queued_as: 'inline:7' } },
    });

    renderApp(<IntakePage />);
    await userEvent.click(await screen.findByTestId('start-run'));

    expect(await screen.findByText(/Прогон №7/)).toBeInTheDocument();
  });

  it('E12: активный прогон отвечает отказом с его номером', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': { status: 200, body: OK_ESTIMATE },
      '/api/runs': { status: 409, body: { detail: 'прогон 4 уже идёт: второй стоит вторую цену' } },
    });

    renderApp(<IntakePage />);
    await userEvent.click(await screen.findByTestId('start-run'));

    expect(await screen.findByText(/прогон 4 уже идёт/)).toBeInTheDocument();
  });

  it('E13: после приёма смета пересчитывается — список изменился, цена другая', async () => {
    rememberToken('токен');
    server({
      '/api/runs/estimate': [
        { status: 200, body: { ...OK_ESTIMATE, projects: 0, units_estimated: 0 } },
        { status: 200, body: OK_ESTIMATE },
      ],
      '/api/intake/file': { status: 200, body: REPORT },
    });

    renderApp(<IntakePage />);
    expect(await screen.findByText('units по смете 0')).toBeInTheDocument();
    await upload();

    await waitFor(() => expect(screen.getByText('units по смете 1980')).toBeInTheDocument());
  });
});

/**
 * Журнал прогонов и расход units. Примеры приёмки E1–E10.
 *
 * Проверяется то, ради чего эти экраны есть: видно ли, что прогон идёт и чем
 * кончился, и видно ли, сколько денег осталось — включая случай «остаток
 * неизвестен», который нельзя показывать нулём.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { RunsPage } from '../RunsPage';
import { UsagePage } from '../UsagePage';

function run(id: number, status: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    status,
    started_by: 1,
    started_by_name: 'Сотрудник PR',
    started_by_deleted: false,
    created_at: '2026-09-11T10:00:00Z',
    started_at: '2026-09-11T10:00:05Z',
    finished_at: status === 'running' || status === 'queued' ? null : '2026-09-11T11:30:00Z',
    projects_total: 10,
    projects_skipped: 0,
    projects_ok: 10,
    projects_failed: 0,
    units_estimated: 2112,
    units_actual: 1936,
    error: '',
    ...extra,
  };
}

function server(routes: Record<string, { status: number; body: unknown }>): { calls: string[] } {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      calls.push(url);
      const path = url.split('?')[0] ?? url;
      const found = Object.entries(routes).find(([route]) => path.endsWith(route));
      const reply = found?.[1] ?? { status: 404, body: { detail: 'нет пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return { calls };
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('журнал прогонов', () => {
  it('E1 и E4: строки с числами, у упавшего видна причина', async () => {
    server({
      '/api/runs': {
        status: 200,
        body: [
          run(3, 'failed', { error: 'Ahrefs не отвечает', projects_ok: 4, projects_failed: 6 }),
          run(2, 'done'),
        ],
      },
    });

    renderApp(<RunsPage />);

    expect(await screen.findByText('Ahrefs не отвечает')).toBeInTheDocument();
    expect(screen.getByText('упало 6')).toBeInTheDocument();
    // Смета и факт рядом: расхождение видно сразу, а не после подсчёта.
    expect(screen.getAllByText(/2 112 → 1 936/)).not.toHaveLength(0);
  });

  it('E3: завершённые прогоны не опрашиваются', async () => {
    const { calls } = server({ '/api/runs': { status: 200, body: [run(2, 'done')] } });

    renderApp(<RunsPage />);
    await screen.findByText('готов');
    const after = calls.length;
    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(calls.length).toBe(after);
    expect(screen.queryByText(/журнал обновляется сам/)).not.toBeInTheDocument();
  });

  it('E2: идущий прогон переводит экран в режим самообновления', async () => {
    server({ '/api/runs': { status: 200, body: [run(4, 'running'), run(3, 'done')] } });

    renderApp(<RunsPage />);

    expect(await screen.findByText(/журнал обновляется сам/)).toBeInTheDocument();
  });

  it('E13: статус прогона показан по-русски', async () => {
    // «done» посреди русского экрана — enum, а не исход. Человек читает исход.
    server({ '/api/runs': { status: 200, body: [run(2, 'done'), run(1, 'rejected')] } });

    renderApp(<RunsPage />);

    expect(await screen.findByText('готов')).toBeInTheDocument();
    // «Отклонён по квоте» — не «упал»: прогон не начинался и units не потрачены.
    expect(screen.getByText('отклонён по квоте')).toBeInTheDocument();
    expect(screen.queryByText('done')).not.toBeInTheDocument();
  });

  it('E14: незнакомый статус не выдумывается', async () => {
    // Сервис знает больше экрана: сырое значение честнее придуманного слова.
    server({ '/api/runs': { status: 200, body: [run(9, 'reaped')] } });

    renderApp(<RunsPage />);

    expect(await screen.findByText('reaped')).toBeInTheDocument();
  });

  it('E5: пустой журнал говорит словами и подсказывает, где запустить', async () => {
    server({ '/api/runs': { status: 200, body: [] } });

    renderApp(<RunsPage />);

    expect(await screen.findByText(/Прогонов ещё не было/)).toBeInTheDocument();
  });

  it('E10: отказ показан текстом сервера', async () => {
    server({ '/api/runs': { status: 403, body: { detail: 'нет права read: группа user' } } });

    renderApp(<RunsPage />);

    expect(await screen.findByText(/нет права read/)).toBeInTheDocument();
  });
});

describe('пропуски прогона', () => {
  it('E1: «пропущено 2» раскрывается в домены с причинами', async () => {
    // ТЗ требует «сколько обработано, сколько пропущено и почему». До этой
    // поставки экран показывал «8 из 10» и молчал о двух.
    const card = {
      ...run(7, 'partial', { projects_ok: 8, projects_skipped: 2 }),
      fates: [
        {
          domain: 'молодой.example',
          outcome: 'skipped_no_data',
          reason: 'у домена нет истории: два пустых ответа подряд',
          units_actual: 0,
        },
      ],
    };
    server({
      '/api/runs': {
        status: 200,
        body: [run(7, 'partial', { projects_ok: 8, projects_skipped: 2 })],
      },
      '/api/runs/7': { status: 200, body: card },
    });

    renderApp(<RunsPage />);
    const why = await screen.findByText('почему');
    await userEvent.click(why);

    expect(await screen.findByText('молодой.example')).toBeInTheDocument();
    // Исход — словом, а не значением перечисления.
    expect(screen.getByText('пропущен: нет данных')).toBeInTheDocument();
    expect(screen.getByText(/нет истории/)).toBeInTheDocument();
  });

  it('E3: у прогона без пропусков лишнего на экране нет', async () => {
    server({ '/api/runs': { status: 200, body: [run(8, 'done')] } });

    renderApp(<RunsPage />);

    await screen.findByText('готов');
    expect(screen.queryByText('почему')).not.toBeInTheDocument();
    expect(screen.queryByText(/пропущено/)).not.toBeInTheDocument();
  });
});

describe('расход units', () => {
  const USAGE = {
    spent: 5872,
    reserved: 2112,
    remaining: 9500,
    uncounted: 0,
    per_hundred_domains: 21120,
  };

  it('E6: потрачено, резерв и остаток — три разных числа', async () => {
    server({
      '/api/usage': { status: 200, body: USAGE },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    expect(await screen.findByText('потрачено 5 872')).toBeInTheDocument();
    // Резерв отдельно: без него остаток выглядит больше, чем есть.
    expect(screen.getByText('удержано резервом 2 112')).toBeInTheDocument();
    expect(screen.getByText('остаток 9 500')).toBeInTheDocument();
    expect(screen.getByText(/21 120 units/)).toBeInTheDocument();
  });

  it('E7: неизвестный остаток — слово, а не ноль', async () => {
    server({
      '/api/usage': { status: 200, body: { ...USAGE, remaining: null, per_hundred_domains: null } },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    // Ноль читался бы как «квота кончилась» — то есть как запрет запускать.
    expect(await screen.findByText('остаток неизвестен')).toBeInTheDocument();
    expect(screen.getByText(/прогонов не было/)).toBeInTheDocument();
  });

  it('E11: расход, которого счётчик Ahrefs ещё не видит, назван отдельно', async () => {
    // Замер 13.09.2026: счётчик отстаёт, а резерв снимается вместе со статусом
    // прогона. Покажи мы один остаток — оператор увидел бы «хватает» там, где
    // прогон оборвётся на середине.
    server({
      '/api/usage': { status: 200, body: { ...USAGE, uncounted: 2262 } },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    expect(await screen.findByText('остаток 9 500')).toBeInTheDocument();
    expect(screen.getByText('счётчик Ahrefs ещё не видит 2 262')).toBeInTheDocument();
    // Число, по которому считается прогон, названо прямо: 9500 − 2262.
    expect(screen.getByText(/остатку 7 238 units/)).toBeInTheDocument();
  });

  it('E12: нечего вычитать — лишних чисел на экране нет', async () => {
    server({
      '/api/usage': { status: 200, body: USAGE },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    await screen.findByText('остаток 9 500');
    expect(screen.queryByText(/счётчик Ahrefs ещё не видит/)).not.toBeInTheDocument();
  });

  it('E8: степени алертов различаются', async () => {
    server({
      '/api/usage': { status: 200, body: USAGE },
      '/api/alerts': {
        status: 200,
        body: [
          { kind: 'units_low', severity: 'critical', message: 'остаток units 300 ниже порога' },
          { kind: 'cases_ready', severity: 'good', message: 'пачка кейсов готова' },
        ],
      },
    });

    renderApp(<UsagePage />);
    await screen.findByText(/остаток units 300/);

    const severities = [...document.querySelectorAll('[data-severity]')].map((node) =>
      node.getAttribute('data-severity'),
    );
    expect(severities).toEqual(['critical', 'good']);
  });

  it('E9: поводов нет — это ответ, а не тишина', async () => {
    server({
      '/api/usage': { status: 200, body: USAGE },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    expect(await screen.findByText(/Поводов нет/)).toBeInTheDocument();
  });
});

describe('кто запускал прогон', () => {
  it('имя автора в журнале, а удалённый — с пометкой', async () => {
    // Журнал существует ради этого вопроса. Раньше он отвечал на него числом:
    // экран не показывал автора вовсе, а в ответе сервера лежал только id.
    server({
      '/api/runs': {
        status: 200,
        body: [
          run(7, 'done'),
          run(6, 'done', { started_by: 2, started_by_name: 'Уволенный', started_by_deleted: true }),
        ],
      },
    });

    renderApp(<RunsPage />);

    expect(await screen.findByText('Сотрудник PR')).toBeInTheDocument();
    expect(screen.getByText('Уволенный')).toBeInTheDocument();
    // Пометка стоит у того, кого удалили, и только у него.
    const marks = document.querySelectorAll('[data-author-deleted="yes"]');
    expect(marks).toHaveLength(1);
    expect(marks[0]?.closest('td')).toHaveTextContent('Уволенный');
  });
});

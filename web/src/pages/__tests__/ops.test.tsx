/**
 * Журнал прогонов и расход units. Примеры приёмки E1–E10.
 *
 * Проверяется то, ради чего эти экраны есть: видно ли, что прогон идёт и чем
 * кончился, и видно ли, сколько денег осталось — включая случай «остаток
 * неизвестен», который нельзя показывать нулём.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { RunsPage } from '../RunsPage';
/** Раздел живёт в маршрутизаторе: с 15.09.2026 приём списка и журнал — один
 *  экран, и признак открытого окна сметы держится в адресе. */
function showRuns() {
  return renderApp(
    <BrowserRouter>
      <RunsPage />
    </BrowserRouter>,
  );
}
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

    showRuns();

    // Причина отказа уехала в раскрытие (15.09.2026): в ячейке она занимала
    // всю ширину экрана. В таблице остаётся знак вопроса, по нему — причина.
    expect(await screen.findByText('упало 6')).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText('почему пропущены'));
    expect(await screen.findByText(/Ahrefs не отвечает/)).toBeInTheDocument();
    // Смета и факт рядом: расхождение видно сразу, а не после подсчёта.
    expect(screen.getAllByText(/2 112 → 1 936/)).not.toHaveLength(0);
  });

  it('B6: ступень названа под номером — сборка кейсов не выглядит сбором', async () => {
    server({
      '/api/runs': {
        status: 200,
        body: [
          run(9, 'done', { stage: 'cases', projects_ok: 0, projects_skipped: 18 }),
          run(8, 'done', { stage: 'stage2' }),
          run(7, 'done', { stage: '' }),
        ],
      },
    });

    showRuns();

    expect(await screen.findByText('сборка кейсов')).toBeInTheDocument();
    expect(screen.getByText('шаг 2')).toBeInTheDocument();
    // У прогона старше поля ступень неизвестна — и она не выдумывается.
    expect(document.querySelectorAll('[data-stage]')).toHaveLength(2);
  });

  it('E3: завершённые прогоны не опрашиваются', async () => {
    const { calls } = server({ '/api/runs': { status: 200, body: [run(2, 'done')] } });

    showRuns();
    await screen.findByText('готов');
    const after = calls.length;
    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(calls.length).toBe(after);
    expect(screen.queryByText(/журнал обновляется сам/)).not.toBeInTheDocument();
  });

  it('E2: идущий прогон переводит экран в режим самообновления', async () => {
    server({ '/api/runs': { status: 200, body: [run(4, 'running'), run(3, 'done')] } });

    showRuns();

    expect(await screen.findByText(/журнал обновляется сам/)).toBeInTheDocument();
  });

  it('E13: статус прогона показан по-русски', async () => {
    // «done» посреди русского экрана — enum, а не исход. Человек читает исход.
    server({ '/api/runs': { status: 200, body: [run(2, 'done'), run(1, 'rejected')] } });

    showRuns();

    expect(await screen.findByText('готов')).toBeInTheDocument();
    // «Отклонён по квоте» — не «упал»: прогон не начинался и units не потрачены.
    expect(screen.getByText('отклонён по квоте')).toBeInTheDocument();
    expect(screen.queryByText('done')).not.toBeInTheDocument();
  });

  it('E14: незнакомый статус не выдумывается', async () => {
    // Сервис знает больше экрана: сырое значение честнее придуманного слова.
    server({ '/api/runs': { status: 200, body: [run(9, 'reaped')] } });

    showRuns();

    expect(await screen.findByText('reaped')).toBeInTheDocument();
  });

  it('E5: пустой журнал говорит словами и подсказывает, где запустить', async () => {
    server({ '/api/runs': { status: 200, body: [] } });

    showRuns();

    expect(await screen.findByText(/Прогонов ещё не было/)).toBeInTheDocument();
  });

  it('E10: отказ показан текстом сервера', async () => {
    server({ '/api/runs': { status: 403, body: { detail: 'нет права read: группа user' } } });

    showRuns();

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

    showRuns();
    // Слово «почему» заменено жёлтым знаком вопроса: подпись занимала в
    // колонке больше места, чем само число (замечание владельца 15.09.2026).
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect(await screen.findByText('молодой.example')).toBeInTheDocument();
    // Исход — словом, а не значением перечисления.
    expect(screen.getByText('пропущен: нет данных')).toBeInTheDocument();
    expect(screen.getByText(/нет истории/)).toBeInTheDocument();
  });

  it('E3: у прогона без пропусков лишнего на экране нет', async () => {
    server({ '/api/runs': { status: 200, body: [run(8, 'done')] } });

    showRuns();

    await screen.findByText('готов');
    expect(screen.queryByLabelText('почему пропущены')).not.toBeInTheDocument();
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

    showRuns();

    expect(await screen.findByText('Сотрудник PR')).toBeInTheDocument();
    expect(screen.getByText('Уволенный')).toBeInTheDocument();
    // Пометка стоит у того, кого удалили, и только у него.
    const marks = document.querySelectorAll('[data-author-deleted="yes"]');
    expect(marks).toHaveLength(1);
    expect(marks[0]?.closest('td')).toHaveTextContent('Уволенный');
  });
});

describe('длинный текст не раздувает таблицу', () => {
  const TRACE =
    'MissingGreenlet: greenlet_spawn has not been called; ' +
    "can't call await_only() here. Was IO attempted in an unexpected place? " +
    '(Background on this error at: https://sqlalche.me/e/20/xd2s)';

  it('трассировки в таблице нет, но она доступна под знаком вопроса', async () => {
    server({
      '/api/runs': {
        status: 200,
        body: [run(387, 'failed', { error: TRACE, projects_ok: 0, projects_skipped: 19 })],
      },
      '/api/runs/387': {
        status: 200,
        body: { ...run(387, 'failed', { error: TRACE }), fates: [] },
      },
    });

    showRuns();
    await screen.findByText(/пропущено 19/);

    // Ядро замечания: сырая трассировка стояла в ячейке и раздувала колонку.
    expect(screen.queryByText(new RegExp('MissingGreenlet'))).not.toBeInTheDocument();

    // Но она не потеряна: это единственное объяснение упавшего прогона.
    await userEvent.click(screen.getByLabelText('почему пропущены'));
    expect(await screen.findByText(new RegExp('MissingGreenlet'))).toBeInTheDocument();
  });
});

describe('журнал листается и отбирается', () => {
  const PAGE = Array.from({ length: 20 }, (_, index) => run(500 - index, 'done'));

  function journal(rows: unknown, authors: unknown = []) {
    return server({
      '/api/runs/authors': { status: 200, body: authors },
      '/api/runs': { status: 200, body: rows },
    });
  }

  it('полная страница даёт листалку, неполная — нет', async () => {
    journal(PAGE);
    showRuns();

    expect(await screen.findByRole('button', { name: 'Вперёд' })).toBeInTheDocument();
  });

  it('короткий журнал листалку не показывает', async () => {
    journal([run(1, 'done')]);
    showRuns();

    await screen.findByText('готов');
    expect(screen.queryByRole('button', { name: 'Вперёд' })).not.toBeInTheDocument();
  });

  it('отбор по автору уезжает в запрос и в адрес', async () => {
    const net = journal(PAGE, [
      { id: 7, name: 'anthony@ahrefs-cases.local', deleted: false },
      { id: 9, name: 'pr@agency.local', deleted: true },
    ]);
    showRuns();

    // Список авторов приезжает своим запросом: выбирать можно, только когда он
    // приехал, иначе `selectOptions` не находит значения.
    await screen.findByRole('option', { name: /pr@agency.local/ });
    await userEvent.selectOptions(screen.getByLabelText('Кто запустил'), '9');

    await waitFor(() => expect(net.calls.some((url) => url.includes('started_by=9'))).toBe(true));
    expect(new URLSearchParams(window.location.search).get('кто')).toBe('9');
  });

  it('удалённый автор остаётся в отборе и помечен', async () => {
    journal(PAGE, [{ id: 9, name: 'pr@agency.local', deleted: true }]);
    showRuns();

    // Журнал живёт ради вопроса «кто запускал»: вместе с уволившимся из отбора
    // пропали бы и его прогоны.
    expect(
      await screen.findByRole('option', { name: /pr@agency.local \(удалён\)/ }),
    ).toBeInTheDocument();
  });

  it('даты уезжают в запрос обеими границами', async () => {
    const net = journal(PAGE);
    showRuns();

    await userEvent.type(await screen.findByLabelText('С даты'), '2026-09-13');
    await userEvent.type(screen.getByLabelText('По дату'), '2026-09-13');

    await waitFor(() =>
      expect(
        net.calls.some(
          (url) => url.includes('since=2026-09-13') && url.includes('until=2026-09-13'),
        ),
      ).toBe(true),
    );
  });

  it('пустой ответ под отбором объясняется иначе, чем пустой журнал', async () => {
    journal([], [{ id: 9, name: 'pr@agency.local', deleted: false }]);
    showRuns();

    expect(await screen.findByText(/Прогонов ещё не было/)).toBeInTheDocument();

    await screen.findByRole('option', { name: /pr@agency.local/ });
    await userEvent.selectOptions(screen.getByLabelText('Кто запустил'), '9');

    // «Ничего не нашлось» лечится снятием отбора, «ничего не было» — запуском.
    expect(await screen.findByText(/Под этот отбор прогонов нет/)).toBeInTheDocument();
  });
});

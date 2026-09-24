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

describe('раскрытие показывает только проблемы', () => {
  /** Судьбы прогона такими, какими их отдаёт живой API: все исходы подряд.
   *  E1 держал в ответе один пропущенный домен и потому не видел, что
   *  раскрытие рисует и собранные — на проде это 51 строка «собран» из 53. */
  function fatesRun(
    fates: { domain: string; outcome: string; reason?: string; project_deleted?: boolean }[],
  ) {
    const card = {
      ...run(12, 'partial', { projects_ok: 3, projects_skipped: 2 }),
      fates: fates.map((fate) => ({ reason: '', units_actual: 132, ...fate })),
    };
    server({
      '/api/runs': {
        status: 200,
        body: [run(12, 'partial', { projects_ok: 3, projects_skipped: 2 })],
      },
      '/api/runs/12': { status: 200, body: card },
    });
  }

  it('в раскрытии только те, кого прогон не собрал', async () => {
    fatesRun([
      { domain: 'kaspi.kz', outcome: 'ok', reason: 'вся история уже собрана' },
      { domain: 'lonelyplanet.com', outcome: 'skipped_no_data', reason: 'Ahrefs не отдал историю' },
      { domain: 'bellroy.com', outcome: 'ok' },
      { domain: 'huel.com', outcome: 'failed', reason: 'Ahrefs ответил 500' },
      { domain: 'kiwi.com', outcome: 'ok' },
    ]);

    showRuns();
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect(await screen.findByText('lonelyplanet.com')).toBeInTheDocument();
    expect(screen.getByText('huel.com')).toBeInTheDocument();
    // Собранных в раскрытии нет — ни доменом, ни словом исхода.
    expect(screen.queryByText('kaspi.kz')).not.toBeInTheDocument();
    expect(screen.queryByText('собран')).not.toBeInTheDocument();
    // Но и не пропали молча: их число названо одной строкой.
    expect(screen.getByText('без замечаний собрано: 3')).toBeInTheDocument();
  });

  it('две кампании одного сайта с проблемой — две строки', async () => {
    // Обе строки React нарисует и с одинаковым ключом — но с предупреждением,
    // и при следующем обновлении списка вправе потерять одну из них. Поэтому
    // тест смотрит и на ключи: домен у двух кампаний один и тот же.
    const complaints = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    fatesRun([
      { domain: 'nordvpn.com', outcome: 'skipped_no_data', reason: 'первая кампания' },
      { domain: 'nordvpn.com', outcome: 'skipped_quota', reason: 'вторая кампания' },
      { domain: 'kiwi.com', outcome: 'ok' },
    ]);

    showRuns();
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect(await screen.findByText('первая кампания')).toBeInTheDocument();
    expect(screen.getByText('вторая кампания')).toBeInTheDocument();
    expect(screen.getAllByText('nordvpn.com')).toHaveLength(2);
    const sameKey = complaints.mock.calls.filter((call) => String(call[0]).includes('same key'));
    complaints.mockRestore();
    expect(sameKey).toHaveLength(0);
  });

  it('K7: удалённый проект подписан, живая кампания того же сайта — нет', async () => {
    fatesRun([
      {
        domain: 'nordvpn.com',
        outcome: 'skipped_no_data',
        reason: 'первая',
        project_deleted: true,
      },
      { domain: 'nordvpn.com', outcome: 'skipped_quota', reason: 'вторая' },
      { domain: 'kiwi.com', outcome: 'ok', project_deleted: true },
      { domain: 'bellroy.com', outcome: 'ok' },
    ]);

    showRuns();
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect((await screen.findByText('первая')).closest('tr')).toHaveTextContent('(проект удалён)');
    expect(screen.getByText('вторая').closest('tr')).not.toHaveTextContent('(проект удалён)');
    // Собранные не перечисляются, но удалённые среди них названы числом.
    expect(screen.getByText(/без замечаний собрано: 2/)).toHaveTextContent(
      'без замечаний собрано: 2, из них проектов удалено: 1',
    );
  });

  it('проблем нет — таблицы нет, одна строка', async () => {
    fatesRun([
      { domain: 'kiwi.com', outcome: 'ok' },
      { domain: 'bellroy.com', outcome: 'ok' },
    ]);

    showRuns();
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect(await screen.findByText('без замечаний собрано: 2')).toBeInTheDocument();
    expect(screen.queryByText('kiwi.com')).not.toBeInTheDocument();
  });
});

describe('журнал сборки кейсов', () => {
  /** Судьбы прогона сборки кейсов в пропорциях прода 24.09.2026 (10 собрано,
   *  41 «плохой», 2 «данных не хватило») и по одной на оставшиеся исходы — в
   *  порядке, в котором их отдаёт API: по домену, вперемешку (урок L214). */
  function casesRun() {
    const fates = [
      ...Array.from({ length: 10 }, (_, i) => ({
        domain: `built${i}.example`,
        outcome: 'ok',
        reason: `кейс собран: built${i}.example — Кейс v3.pdf`,
      })),
      ...Array.from({ length: 41 }, (_, i) => ({
        domain: `c${i}.example`,
        outcome: 'case_not_eligible',
        reason: 'группа «плохой»: кейс по ТЗ собирают хорошим и средним',
      })),
      { domain: 'a-thin.example', outcome: 'case_insufficient_data', reason: 'первая' },
      { domain: 'd-thin.example', outcome: 'case_insufficient_data', reason: 'вторая' },
      {
        domain: 'b-live.example',
        outcome: 'case_verdict_mismatch',
        reason:
          'вердикт вынесен по рядам «live», а показаны «fixture» — переклассифицируйте по рядам «live»',
      },
      { domain: 'ozon.ru', outcome: 'case_blocked', reason: 'контент-запрет: гео: «RU»' },
    ]
      .sort((a, b) => a.domain.localeCompare(b.domain))
      .map((fate) => ({ units_actual: 0, ...fate }));
    const row = run(31, 'done', {
      stage: 'cases',
      projects_total: 55,
      projects_ok: 10,
      projects_skipped: 45,
    });
    server({
      '/api/runs': { status: 200, body: [row] },
      '/api/runs/31': { status: 200, body: { ...row, fates } },
    });
  }

  it('Y6: строками — только то, что требует действия; собранные и «плохие» — числом', async () => {
    casesRun();

    showRuns();
    await userEvent.click(await screen.findByLabelText('почему пропущены'));

    expect(await screen.findByText('a-thin.example')).toBeInTheDocument();
    expect(screen.getAllByText('данных не хватило')).toHaveLength(2);
    expect(screen.getByText('вердикт не про эти данные')).toBeInTheDocument();
    expect(screen.getByText(/переклассифицируйте по рядам «live»/)).toBeInTheDocument();
    expect(screen.getByText('не отдан: контент-запрет')).toBeInTheDocument();
    expect(document.querySelectorAll('tr[data-fate]')).toHaveLength(4);
    expect(screen.getByText('без замечаний собрано: 10')).toBeInTheDocument();
    expect(screen.getByText('не положен по группе: 41')).toBeInTheDocument();
    expect(screen.queryByText('c0.example')).not.toBeInTheDocument();
  });
});

const USAGE = {
  spent: 5872,
  conditional: 0,
  reserved: 2112,
  remaining: 9500,
  uncounted: 0,
  live_domains: 28,
  per_hundred_domains: 21120,
};

describe('расход units', () => {
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

describe('расход units: только живые прогоны', () => {
  it('R6: стенд с одними fixture-прогонами — условные units названы, а не выданы за расход', async () => {
    // Как на проде до живого ключа: живого расхода нет, fixture-прогоны
    // насчитали условные units. Прежний текст «прогонов не было» здесь был бы
    // неправдой: прогоны были, в Ahrefs они не ходили.
    server({
      '/api/usage': {
        status: 200,
        body: {
          ...USAGE,
          spent: 0,
          conditional: 15414,
          live_domains: 0,
          per_hundred_domains: null,
        },
      },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    expect(await screen.findByText('потрачено 0')).toBeInTheDocument();
    expect(screen.getByText(/^Условные units: 15 414 — /)).toBeInTheDocument();
    expect(screen.getByText(/живых прогонов с расходом ещё не было/)).toBeInTheDocument();
    expect(screen.queryByText(/прогонов не было/)).not.toBeInTheDocument();
  });

  it('R7: стоимость на сто доменов — со своими слагаемыми, без строки об условных units', async () => {
    server({
      '/api/usage': {
        status: 200,
        body: {
          ...USAGE,
          spent: 11952,
          conditional: 0,
          live_domains: 62,
          per_hundred_domains: 19277,
        },
      },
      '/api/alerts': { status: 200, body: [] },
    });

    renderApp(<UsagePage />);

    expect(
      await screen.findByText(
        'Стоимость запуска на сто доменов по факту: 19 277 units (потрачено 11 952 units, оплачено доменов — 62).',
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Условные units/)).not.toBeInTheDocument();
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

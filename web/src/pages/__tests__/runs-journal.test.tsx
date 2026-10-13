/**
 * Журнал прогонов держит одно состояние, пока идёт цикл (Z60). Примеры M123, M124.
 *
 * Найдено владельцем 13.10.2026 на проде: строка цикла проходит ступени, а
 * таблица «то уже, то шире». Вёрстки в jsdom нет — здесь проверяется то, от чего
 * ширины перестают зависеть от содержимого: таблица задаёт их сама, ступень —
 * одна строка, даты — две во всех состояниях. Сами пиксели меряются в Chrome на
 * стенде по тем же шести состояниям (verify-report).
 */
import { screen, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderApp } from '../../test/render';
import { RunsPage } from '../RunsPage';

/** Строки журнала прода 13.10 (L214): ниже цикла — сборка, данные под кейс и шаг 1. */
function row(id: number, stage: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    status: 'done',
    started_by: 1,
    started_by_name: 'anthony@parsingprices.com',
    started_by_deleted: false,
    stage,
    created_at: '2026-10-13T09:26:00Z',
    started_at: '2026-10-13T09:26:01Z',
    finished_at: '2026-10-13T09:26:40Z',
    projects_total: 12,
    projects_ok: 12,
    projects_failed: 0,
    projects_skipped: 0,
    units_estimated: 100,
    units_actual: 100,
    error: '',
    live: true,
    mode: 'live',
    pack: false,
    pack_cases: 0,
    build_cases: false,
    current_stage: '',
    ...extra,
  };
}

const OLDER = [
  row(23, 'cases', {
    projects_total: 55,
    projects_skipped: 43,
    units_estimated: 0,
    units_actual: 0,
    pack: true,
    pack_cases: 12,
  }),
  row(22, 'case_data'),
  row(20, 'stage1', {
    started_by_name: 'Vladimir',
    projects_total: 55,
    projects_ok: 55,
    units_estimated: 0,
    units_actual: 0,
  }),
];

/** Шесть состояний строки цикла №28 — как она шла на проде 13.10. */
function cycle(status: string, current: string, extra: Record<string, unknown> = {}) {
  return row(28, 'cycle', {
    status,
    current_stage: current,
    started_at: status === 'queued' ? null : '2026-10-13T10:10:01Z',
    finished_at: null,
    projects_total: 1,
    projects_ok: 0,
    units_estimated: 354,
    units_actual: 0,
    ...extra,
  });
}

/** Середина цикла — ступень с самой длинной подписью. */
const CASE_DATA = cycle('running', 'case_data', { units_actual: 177 });

/** Состояние и что пишет ступень: пока идёт — какая, кончился — что это за прогон. */
const STATES: [string, ReturnType<typeof cycle>, string][] = [
  ['в очереди', cycle('queued', ''), 'цикл по файлу'],
  ['шаг 1', cycle('running', 'stage1'), 'цикл · шаг 1'],
  ['шаг 2', cycle('running', 'stage2', { units_actual: 77 }), 'цикл · шаг 2'],
  ['данные под кейс', CASE_DATA, 'цикл · данные под кейс'],
  ['сборка кейсов', cycle('running', 'cases', { units_actual: 304 }), 'цикл · сборка кейсов'],
  [
    'готов',
    cycle('done', 'cases', {
      units_actual: 304,
      projects_ok: 1,
      pack: true,
      pack_cases: 1,
      finished_at: '2026-10-13T10:11:02Z',
    }),
    'цикл по файлу',
  ],
];

function serve(rows: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = url.split('?')[0] ?? url;
      const body = path.endsWith('/api/runs/authors') ? [] : path.endsWith('/api/runs') ? rows : [];
      return new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

async function journal(rows: unknown[]) {
  serve(rows);
  renderApp(
    <BrowserRouter>
      <RunsPage />
    </BrowserRouter>,
  );
  const table = (await screen.findByText('Units: смета → факт')).closest(
    'table',
  ) as HTMLTableElement;
  return table;
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('журнал держит одно состояние (Z60)', () => {
  it('M123: таблица задаёт ширины колонок сама — доли в сумме 100 %', async () => {
    const table = await journal([CASE_DATA, ...OLDER]);

    expect(table.style.getPropertyValue('--table-layout')).toBe('fixed');
    const shares = [...table.querySelectorAll('thead th')].map(
      (th) => (th as HTMLElement).style.width,
    );
    expect(shares.every((width) => width.endsWith('%'))).toBe(true);
    expect(shares.reduce((sum, width) => sum + Number.parseFloat(width), 0)).toBe(100);
  });

  it.each(STATES)(
    'M123: строка цикла (%s) — номер и ступень одной строкой, даты двумя',
    async (_name, state, stageLine) => {
      const table = await journal([state, ...OLDER]);
      const line = table.querySelector('tr[data-run="28"]') as HTMLTableRowElement;

      const stage = within(line).getByText(stageLine);
      expect(stage).toHaveStyle({ whiteSpace: 'nowrap' });
      const cells = line.querySelectorAll('td');
      // «Начат» и «Завершён»: дата и время — двумя строками, как номер и ступень.
      for (const [index, when] of [
        [3, state.started_at ?? state.created_at],
        [4, state.finished_at],
      ] as const) {
        expect((cells[index] as HTMLElement).children).toHaveLength(when ? 2 : 1);
      }
    },
  );

  it('M124: «Что дальше» держит высоту — подсказка не двигает журнал', async () => {
    await journal([CASE_DATA, ...OLDER]);

    const hint = (await screen.findByText(/сейчас данные под кейс/)).closest(
      '[data-next-step]',
    ) as HTMLElement;
    expect(hint.style.minHeight).not.toBe('');
  });
});

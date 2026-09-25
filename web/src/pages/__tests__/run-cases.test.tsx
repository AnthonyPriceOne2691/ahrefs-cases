/**
 * Кейсы из строки журнала. Примеры приёмки R1–R5.
 *
 * Просьба владельца 25.09.2026: «выгрузить кейсы по прогону кнопочкой на
 * прогоне». У сборки — «Скачать N кейсов» (копия, которую отложил прогон), у
 * последнего «данные под кейс» — «Собрать кейсы».
 */
import { waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import type { RunRow } from '../../api/types';
import { renderScreen } from '../../test/render';
import { casesCount } from '../format';
import { RunsPage } from '../RunsPage';

function run(id: number, stage: string, extra: Partial<RunRow> = {}): RunRow {
  return {
    id,
    status: 'done',
    started_by: 1,
    started_by_name: 'Сотрудник SEO',
    started_by_deleted: false,
    stage,
    created_at: '2026-09-25T13:47:16Z',
    started_at: '2026-09-25T13:47:17Z',
    finished_at: '2026-09-25T13:47:19Z',
    projects_total: 54,
    projects_ok: 0,
    projects_failed: 0,
    projects_skipped: 54,
    units_estimated: 0,
    units_actual: 0,
    error: '',
    live: true,
    mode: 'live',
    pack: false,
    pack_cases: 0,
    build_cases: false,
    ...extra,
  };
}

interface Reply {
  status: number;
  body: unknown;
  raw?: Blob;
}

function server(rows: RunRow[], extra: Record<string, Reply> = {}): { calls: string[] } {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = url.split('?')[0] ?? url;
      calls.push(`${init?.method ?? 'GET'} ${path}`);
      const found = Object.entries(extra).find(([route]) => path.endsWith(route))?.[1];
      if (found?.raw) {
        return new Response(found.raw, {
          status: found.status,
          headers: { 'content-disposition': "attachment; filename*=utf-8''packed.zip" },
        });
      }
      if (found) return new Response(JSON.stringify(found.body), { status: found.status });
      return new Response(JSON.stringify(path.endsWith('/api/runs') ? rows : []), { status: 200 });
    }),
  );
  return { calls };
}

function row(runId: number): HTMLElement {
  const found = document.querySelector<HTMLElement>(`[data-run="${runId}"]`);
  if (!found) throw new Error(`строки прогона ${runId} нет`);
  return found;
}

let saved: string | null = null;

beforeEach(() => {
  rememberToken('токен');
  saved = null;
  // Как в `cases.test.tsx`: наследник `URL`, а не правка общего класса, — и
  // перехват клика ссылки, в которую уходит файл (jsdom не скачивает).
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = vi.fn(() => 'blob:пачка');
      static revokeObjectURL = vi.fn();
    },
  );
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved = this.download;
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  forgetToken();
  window.history.pushState({}, '', '/');
});

describe('кейсы из строки журнала', () => {
  it('R1: у сборки с копией — «Скачать 11 кейсов», и качается копия этого прогона', async () => {
    const { calls } = server([run(12, 'cases', { pack: true, pack_cases: 11 })], {
      '/api/runs/12/pack': { status: 200, body: null, raw: new Blob(['zip']) },
    });
    renderScreen(<RunsPage />);

    const take = await within(await waitFor(() => row(12))).findByRole('button', {
      name: 'Скачать 11 кейсов',
    });
    await userEvent.click(take);

    await waitFor(() => expect(saved).toBe('packed.zip'));
    expect(calls).toContain('GET /api/runs/12/pack');
  });

  it('R2: у последнего «данные под кейс» — «Собрать кейсы», и сборка запускается', async () => {
    const { calls } = server([run(11, 'case_data', { build_cases: true })], {
      '/api/runs/cases': { status: 202, body: { run_id: 13 } },
    });
    renderScreen(<RunsPage />);

    const build = await within(await waitFor(() => row(11))).findByRole('button', {
      name: 'Собрать кейсы',
    });
    await userEvent.click(build);

    await waitFor(() => expect(calls).toContain('POST /api/runs/cases'));
  });

  it('R3: у остальных прогонов кнопок нет', async () => {
    server([run(8, 'stage1'), run(9, 'cases'), run(4, 'case_data')]);
    renderScreen(<RunsPage />);

    await waitFor(() => row(8));
    for (const runId of [8, 9, 4]) {
      expect(
        within(row(runId)).queryByRole('button', { name: /Скачать|Собрать кейсы/ }),
      ).toBeNull();
    }
  });

  it('R4: отказ выдачи — словами сервера под кнопкой', async () => {
    const detail = 'в пачке этого прогона кейс удалённого проекта — её больше не отдаём';
    server([run(12, 'cases', { pack: true, pack_cases: 2 })], {
      '/api/runs/12/pack': { status: 409, body: { detail } },
    });
    renderScreen(<RunsPage />);

    await userEvent.click(
      await within(await waitFor(() => row(12))).findByRole('button', { name: 'Скачать 2 кейса' }),
    );

    expect(await within(row(12)).findByText(detail)).toBeInTheDocument();
  });

  it('R5: число с согласованным словом', () => {
    expect([1, 2, 5, 11, 21, 22, 111].map(casesCount)).toEqual([
      '1 кейс',
      '2 кейса',
      '5 кейсов',
      '11 кейсов',
      '21 кейс',
      '22 кейса',
      '111 кейсов',
    ]);
  });
});

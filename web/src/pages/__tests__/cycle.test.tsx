/**
 * Цикл по загруженному списку. Примеры приёмки G1–G3.
 *
 * Решение владельца 25.09.2026: «прикрепил ссылку или файл — логика
 * проанализировала — предварительная смета — стартует прогон — в журнале
 * строка с неактивной кнопкой скачать — по окончании кнопка активна».
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { renderScreen } from '../../test/render';
import { RunsPage } from '../RunsPage';

const ESTIMATE = {
  projects: 1,
  units_estimated: 300,
  requests_planned: 6,
  requests_cached: 0,
  scheme_lines: [
    'шаг 2 и данные под кейс посчитаны по нынешним кандидатам и новым проектам — это верхняя граница',
  ],
  quota_left: 9900,
  quota_reserved: 0,
  verdict: 'ok',
  may_start: true,
  reason: '',
};

const REPORT = {
  origin: 'Новая таблица.xlsx',
  accepted: 1,
  created: 1,
  updated: 0,
  rejected_rows: 0,
  by_reason: {},
  rejections: [],
  notices: [],
  project_ids: [54],
};

function cycleRow(status: string, extra: Record<string, unknown> = {}) {
  return {
    id: 12,
    status,
    started_by: 3,
    started_by_name: 'Vladimir',
    started_by_deleted: false,
    stage: 'cycle',
    created_at: '2026-09-25T16:00:00Z',
    started_at: '2026-09-25T16:00:01Z',
    finished_at: status === 'running' ? null : '2026-09-25T16:00:30Z',
    projects_total: 1,
    projects_ok: 1,
    projects_failed: 0,
    projects_skipped: 0,
    units_estimated: 300,
    units_actual: 250,
    error: '',
    live: true,
    mode: 'live',
    pack: false,
    pack_cases: 0,
    build_cases: false,
    current_stage: 'stage2',
    ...extra,
  };
}

interface Seen {
  calls: string[];
  bodies: Record<string, unknown>;
}

/** Ответ по «МЕТОД путь»; прочие GET — пустые списки. */
function server(routes: Record<string, { status: number; body: unknown }>): Seen {
  const seen: Seen = { calls: [], bodies: {} };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const key = `${(init?.method ?? 'GET').toUpperCase()} ${url.split('?')[0] ?? url}`;
      seen.calls.push(`${key}${url.includes('?') ? `?${url.split('?')[1]}` : ''}`);
      if (typeof init?.body === 'string') seen.bodies[key] = JSON.parse(init.body);
      const reply = routes[key] ?? { status: 200, body: [] };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return seen;
}

async function upload() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, new File(['x'], 'Новая таблица.xlsx'), { applyAccept: false });
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
  window.history.pushState({}, '', '/');
});

describe('цикл по загруженному списку', () => {
  it('G1: после загрузки — смета по проектам файла и «Запустить» цикл по ним', async () => {
    rememberToken('токен');
    const seen = server({
      'POST /api/intake/file': { status: 200, body: REPORT },
      'GET /api/runs/chain/estimate': { status: 200, body: ESTIMATE },
      'POST /api/runs/chain': { status: 202, body: { run_id: 12, queued_as: 'run-x' } },
    });
    renderScreen(<RunsPage />);
    await upload();

    expect(await screen.findByText('Весь цикл по этому списку')).toBeInTheDocument();
    expect(seen.calls).toContain('GET /api/runs/chain/estimate?projects=54');
    await userEvent.click(screen.getByRole('button', { name: 'Запустить' }));

    expect(await screen.findByText(/Цикл запущен: прогон №12/)).toBeInTheDocument();
    expect(seen.bodies['POST /api/runs/chain']).toEqual({ project_ids: [54] });
  });

  it('G2: на цикл не хватает units — «Запустить» недоступна, причина видна', async () => {
    rememberToken('токен');
    const reason = 'не хватает units: остаток 100, нужно 300';
    server({
      'POST /api/intake/file': { status: 200, body: REPORT },
      'GET /api/runs/chain/estimate': {
        status: 200,
        body: { ...ESTIMATE, quota_left: 100, verdict: 'not_enough', may_start: false, reason },
      },
    });
    renderScreen(<RunsPage />);
    await upload();

    expect(await screen.findByText(reason)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Запустить' })).toBeDisabled();
  });

  it('G3: строка цикла — шаг внутри и «Скачать» неактивна, пока идёт; в конце — активна', async () => {
    rememberToken('токен');
    server({ 'GET /api/runs': { status: 200, body: [cycleRow('running')] } });
    const view = renderScreen(<RunsPage />);

    const row = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run="12"]');
      if (!found) throw new Error('строки цикла нет');
      return found;
    });
    expect(within(row).getByText('цикл по файлу · шаг 2')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Скачать кейсы' })).toBeDisabled();
    view.unmount();

    server({
      'GET /api/runs': {
        status: 200,
        body: [cycleRow('done', { pack: true, pack_cases: 1 })],
      },
    });
    renderScreen(<RunsPage />);
    const done = await screen.findByRole('button', { name: 'Скачать 1 кейс' });
    expect(done).toBeEnabled();
  });
});

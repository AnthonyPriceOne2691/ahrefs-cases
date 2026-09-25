/**
 * «Что дальше» на экране прогонов. Примеры приёмки N1–N7.
 *
 * Путь до кейсов — три кнопки на двух экранах, и порядок их экран не называл:
 * 25.09.2026 после двух прогонов шага 1 до PDF не дошёл никто. Подсказка читает
 * последний прогон сервиса и называет следующую кнопку.
 */
import { screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import type { RunRow } from '../../api/types';
import { renderScreen } from '../../test/render';
import { RunsPage } from '../RunsPage';
import { nextStep } from '../runs/NextStep';

function run(stage: string, status: string, extra: Partial<RunRow> = {}): RunRow {
  return {
    id: 8,
    status,
    started_by: 3,
    started_by_name: 'Сотрудник SEO',
    started_by_deleted: false,
    stage,
    created_at: '2026-09-25T13:14:17Z',
    started_at: '2026-09-25T13:14:17Z',
    finished_at: status === 'running' || status === 'queued' ? null : '2026-09-25T13:14:18Z',
    projects_total: 54,
    projects_ok: 54,
    projects_failed: 0,
    projects_skipped: 0,
    units_estimated: 50,
    units_actual: 50,
    error: '',
    live: true,
    mode: 'live',
    ...extra,
  };
}

describe('правило «что дальше»', () => {
  it('N1: после шага 1 — «Дособрать кандидатов»', () => {
    const hint = nextStep(run('stage1', 'done'));
    expect(hint?.text).toContain('№8 — шаг 1 — готов');
    expect(hint?.text).toContain('«Дособрать кандидатов»');
    expect(hint?.toCases).toBe(false);
  });

  it('N2: после шага 2 — данные под кейс идут сами, дальше «Кейсы»', () => {
    const hint = nextStep(run('stage2', 'done'));
    expect(hint?.text).toContain('данные под кейс');
    expect(hint?.text).toContain('«Пересобрать кейсы»');
    expect(hint?.toCases).toBe(true);
  });

  it('N3: после данных под кейс — пересобрать и скачать', () => {
    const hint = nextStep(run('case_data', 'done'));
    expect(hint?.text).toContain('«Пересобрать кейсы»');
    expect(hint?.text).toContain('«Скачать ZIP»');
    expect(hint?.toCases).toBe(true);
  });

  it('N4: после сборки кейсов — скачать пачкой или по одному', () => {
    const hint = nextStep(run('cases', 'done'));
    expect(hint?.text).toContain('«Скачать ZIP»');
    expect(hint?.text).toContain('«Скачать PDF»');
    expect(hint?.toCases).toBe(true);
  });

  it('N5: идущий — «когда он закончится»; упавший, отменённый, отклонённый и без ступени — молчат', () => {
    expect(nextStep(run('stage1', 'running'))?.text).toContain('Когда он закончится');
    expect(nextStep(run('stage2', 'queued'))?.text).toContain('Когда он закончится');
    for (const status of ['failed', 'cancelled', 'rejected']) {
      expect(nextStep(run('stage1', status))).toBeNull();
    }
    expect(nextStep(run('', 'done'))).toBeNull();
    expect(nextStep(null)).toBeNull();
  });

  it('N6: «частично» — конец шага: следующий шаг назван, несобранное — в журнале', () => {
    const hint = nextStep(run('stage1', 'partial'));
    expect(hint?.text).toContain('частично');
    expect(hint?.text).toContain('журнал');
    expect(hint?.text).toContain('«Дособрать кандидатов»');
  });
});

describe('подсказка на экране', () => {
  beforeEach(() => rememberToken('токен'));

  afterEach(() => {
    vi.unstubAllGlobals();
    forgetToken();
    window.history.pushState({}, '', '/');
  });

  it('N7: после данных под кейс «Прогоны» ведут на «Кейсы»', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = (typeof input === 'string' ? input : input.toString()).split('?')[0] ?? '';
        const body = path.endsWith('/api/runs') ? [run('case_data', 'done', { id: 10 })] : [];
        return new Response(JSON.stringify(body), { status: 200 });
      }),
    );

    renderScreen(<RunsPage />);

    const hint = await screen.findByText(/№10 — данные под кейс — готов/);
    expect(hint).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Перейти к кейсам' })).toHaveAttribute(
      'href',
      '/cases',
    );
  });
});

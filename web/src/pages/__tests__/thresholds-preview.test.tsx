/**
 * Предпросмотр порогов. Примеры приёмки E1, E3–E6, E9.
 *
 * Проверяется, виден ли каждый из четырёх исходов расчёта — и особенно тот,
 * который легче всего слить с «не изменится»: проект, которому этой версией
 * не хватает купленных месяцев.
 *
 * Условия групп словами проверяет соседний файл: там другой вопрос экрана.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { renderApp } from '../../test/render';
import { ThresholdsPage } from '../ThresholdsPage';

interface Reply {
  status: number;
  body: unknown;
}

const PAYLOAD = {
  version: '2026-09-I',
  windows: {
    point_a_months: 2,
    point_b_months: 2,
    baseline: 'period',
    pre_start_baseline_months: 0,
  },
  eligibility: { min_months_after_start: 3, max_series_gap_months: 2, min_traffic_point_b: 0 },
  groups: {
    good: {
      org_traffic: {
        growth_pct_min: 100,
        growth_abs_min: 2000,
        growth_pct_max: null,
        or_high_pct_low_abs: false,
      },
      supporting_required: 1,
      supporting: { refdomains_growth_pct_min: 50, kw_top10_growth_pct_min: 50 },
      min_months_after_start: 6,
    },
    medium: {
      org_traffic: {
        growth_pct_min: 20,
        growth_abs_min: null,
        growth_pct_max: 100,
        or_high_pct_low_abs: true,
      },
      supporting_required: 0,
      supporting: { refdomains_growth_pct_min: 10, kw_top10_growth_pct_min: 20 },
      min_months_after_start: 3,
    },
  },
  duration: { normalize_after_months: 0 },
  guards: { end_vs_peak_min_pct: 0 },
};

function ruleset(version: string, isActive: boolean, id = 1) {
  return {
    id,
    version,
    is_active: isActive,
    note: 'Приложение А',
    created_at: '2026-09-11T10:00:00Z',
    payload: { ...PAYLOAD, version },
  };
}

function server(routes: Record<string, Reply>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = (url.split('?')[0] ?? url).replace('http://localhost', '');
      const reply = routes[path] ?? { status: 404, body: { detail: 'нет пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
}

const ME = {
  status: 200,
  body: {
    email: 'boss@test.local',
    full_name: 'Руководитель',
    group: 'admin',
    rights: ['read', 'edit_thresholds'],
  },
};

function show() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <ThresholdsPage />
      </BrowserRouter>
    </AuthProvider>,
  );
}

beforeEach(() => rememberToken('токен'));

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('версии', () => {
  it('E1: список версий, действующая помечена', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': {
        status: 200,
        body: [ruleset('2026-09-II', false, 2), ruleset('2026-09-I', true)],
      },
    });

    show();

    expect(await screen.findByText('действующая')).toBeInTheDocument();
    expect(screen.getByText('2026-09-II')).toBeInTheDocument();
  });
});

describe('предпросмотр', () => {
  it('E3 и E4: смена группы, первый вердикт и нехватка данных — три разных списка', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      '/api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 10,
          changes: [{ domain: 'alpha.example', was: 'medium', becomes: 'good' }],
          first_time: [{ domain: 'beta.example', was: null, becomes: 'medium' }],
          unchanged: 6,
          missing_data: ['gamma.example', 'delta.example'],
        },
      },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Что изменится' }));

    // Группы теми же словами, что на экране проектов: «good → poor» посреди
    // русского экрана — то, что показал прогон живого стенда.
    expect(await screen.findByText(/alpha.example: средний → хороший/)).toBeInTheDocument();
    expect(screen.getByText(/beta.example: нет вердикта → средний/)).toBeInTheDocument();
    // Нехватка данных — отдельное состояние: этих проектов версией считать
    // нечем, и «остались в своей группе» про них сказать нельзя (L31).
    expect(screen.getByText(/Данных не хватает: 2/)).toBeInTheDocument();
    expect(screen.getByText(/gamma.example, delta.example/)).toBeInTheDocument();
  });

  it('E5: никто не сменит группу — это сказано словами', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      '/api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 10,
          changes: [],
          first_time: [],
          unchanged: 10,
          missing_data: [],
        },
      },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Что изменится' }));

    expect(await screen.findByText(/Никто не сменит группу/)).toBeInTheDocument();
  });
});

describe('предпросмотр: чего в счёте нет', () => {
  it('E9: «никто не сменит группу» не успокаивает, пока посчитана не вся база', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      '/api/rulesets/2026-09-I/preview': {
        status: 200,
        body: {
          version: '2026-09-I',
          total: 11,
          changes: [],
          first_time: [],
          unchanged: 5,
          missing_data: [
            'a.example',
            'b.example',
            'c.example',
            'd.example',
            'e.example',
            'f.example',
          ],
        },
      },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Что изменится' }));

    // Найдено прогоном живого экрана: пять из одиннадцати посчитаны, шести не
    // хватает данных — и зелёное «всё спокойно» тут читается как вывод о базе.
    expect(await screen.findByText(/посчитано 5 из 11/)).toBeInTheDocument();
    expect(screen.queryByText(/посчитаны все/)).not.toBeInTheDocument();
  });

  it('E6: отказ сервера показан его словами', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
      '/api/rulesets/2026-09-I/preview': {
        status: 404,
        body: { detail: 'нет версии порогов 2026-09-I' },
      },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Что изменится' }));

    expect(await screen.findByText('нет версии порогов 2026-09-I')).toBeInTheDocument();
  });

  it('E7: кнопок правки на этом экране нет вовсе', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    show();
    await screen.findByText('действующая');

    // Право у человека есть, а кнопок нет: правка приедет отдельной поставкой,
    // и экран не должен обещать того, чего пока не делает.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Сохранить/ })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Активировать/ })).not.toBeInTheDocument();
    });
  });
});

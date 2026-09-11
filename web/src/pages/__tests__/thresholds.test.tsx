/**
 * Экран «Пороги»: действующая версия словами. Примеры приёмки E1, E2, E5–E7.
 *
 * Проверяется то, ради чего экран есть: понятны ли условия без JSON. Цифру
 * утверждает Head of Link Building, а не инженер, — и она обязана стоять в
 * предложении, а не в пути `groups.good.org_traffic.growth_pct_min`.
 */
import { screen } from '@testing-library/react';
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

function ruleset(version: string, isActive: boolean, payload: object = PAYLOAD, id = 1) {
  return {
    id,
    version,
    is_active: isActive,
    note: 'Приложение А',
    created_at: '2026-09-11T10:00:00Z',
    payload: { ...payload, version },
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

describe('действующая версия', () => {
  it('E1: показывается та версия, по которой считаются вердикты', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': {
        status: 200,
        body: [ruleset('2026-09-II', false, PAYLOAD, 2), ruleset('2026-09-I', true)],
      },
    });

    show();

    // Свежая версия — не обязательно действующая: сохранение не активирует.
    expect(await screen.findByText(/Действующая версия 2026-09-I/)).toBeInTheDocument();
  });

  it('E2 и E8: условия групп словами, включая вилку «средних»', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    show();

    expect(await screen.findByText('Рост трафика от 100 %')).toBeInTheDocument();
    expect(screen.getByText('И при этом прирост не меньше 2 000 визитов')).toBeInTheDocument();
    expect(screen.getByText(/Подтверждающих метрик нужно 1 из 2/)).toBeInTheDocument();
    expect(screen.getByText('Рост трафика от 20 % до 100 %')).toBeInTheDocument();
    expect(
      screen.getByText('Сюда же попадает сильный рост в процентах при малом приросте в визитах'),
    ).toBeInTheDocument();
  });

  it('ноль в ограничителе — «не задано», а не порог, равный нулю', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 200, body: [ruleset('2026-09-I', true)] },
    });

    show();
    await screen.findByText('Рост трафика от 100 %');

    // «Конец периода не ниже пика на 0 %» читалось бы как работающее правило.
    expect(screen.getAllByText('не задано').length).toBe(2);
  });
});

describe('состояния экрана', () => {
  it('E5: версий нет — сказано, чем это грозит', async () => {
    server({ '/api/auth/me': ME, '/api/rulesets': { status: 200, body: [] } });

    show();

    expect(await screen.findByText(/классифицировать нечем/)).toBeInTheDocument();
  });

  it('E6: отказ сервера показан его словами', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': { status: 403, body: { detail: 'нужно право read' } },
    });

    show();

    expect(await screen.findByText('нужно право read')).toBeInTheDocument();
  });

  it('E7: нереализованная нормализация названа до того, как её попробуют', async () => {
    server({
      '/api/auth/me': ME,
      '/api/rulesets': {
        status: 200,
        body: [
          ruleset('2026-09-I', true, { ...PAYLOAD, duration: { normalize_after_months: 12 } }),
        ],
      },
    });

    show();

    // Версия с ненулевой нормализацией не пройдёт разбор на сервере. Сказать
    // об этом на экране дешевле, чем показать отказ после сохранения.
    expect(await screen.findByText(/нормализация.*не реализована/i)).toBeInTheDocument();
  });
});

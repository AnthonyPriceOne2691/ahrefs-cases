/**
 * Стенд тестов порогов: версия, маршруты сервера и рендер экрана.
 *
 * Три файла тестов (просмотр, предпросмотр, правка) держали одинаковые двести
 * строк подготовки. Копии расходятся молча: поправив `PAYLOAD` в одном месте,
 * получаешь зелёные тесты, проверяющие разные версии одного экрана.
 */
import { BrowserRouter } from 'react-router-dom';
import { vi } from 'vitest';

import { ThresholdsPage } from '../pages/ThresholdsPage';
import { AuthProvider } from '../auth/AuthProvider';

import { renderApp } from './render';

export interface Reply {
  status: number;
  body: unknown;
}

export interface Call {
  url: string;
  method: string;
  body: Record<string, unknown> | null;
}

/** Пороги «Приложения А»: те же числа, что в `config/thresholds.default.yml`. */
export const PAYLOAD = {
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

export function ruleset(version: string, isActive: boolean, payload: object = PAYLOAD, id = 1) {
  return {
    id,
    version,
    is_active: isActive,
    note: 'Приложение А',
    created_at: '2026-09-11T10:00:00Z',
    payload: { ...payload, version },
  };
}

/** Маршруты задаются как «МЕТОД путь»: список версий и сохранение живут по
 *  одному адресу и различаются только методом. */
export function server(routes: Record<string, Reply>): { calls: Call[] } {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = decodeURIComponent((url.split('?')[0] ?? url).replace('http://localhost', ''));
      const method = init?.method ?? 'GET';
      calls.push({
        url: path,
        method,
        body:
          typeof init?.body === 'string'
            ? (JSON.parse(init.body) as Record<string, unknown>)
            : null,
      });
      const reply = routes[`${method} ${path}`] ?? { status: 404, body: { detail: 'нет пути' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return { calls };
}

export function me(rights: string[]): Reply {
  return {
    status: 200,
    body: { email: 'boss@test.local', full_name: 'Руководитель', group: 'admin', rights },
  };
}

export function showThresholds() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <ThresholdsPage />
      </BrowserRouter>
    </AuthProvider>,
  );
}

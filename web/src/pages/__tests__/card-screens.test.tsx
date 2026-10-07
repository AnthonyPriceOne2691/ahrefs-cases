/**
 * Скрины для брифа на карточке. Примеры приёмки M61–M63 и M65–M67 поставки
 * `screenshots-screen`; M64 (ужатие до отправки) — в `shrink.test.ts`.
 *
 * Подменный сервер отвечает по «МЕТОД путь», длиннейший путь выигрывает: список
 * скринов и карточка делят префикс адреса. Ответ может быть функцией — список
 * после загрузки и удаления другой. Картинка отдаётся байтами с типом, как с
 * настоящего сервера: экран обязан превратить её в `data:`-адрес.
 */
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { renderApp } from '../../test/render';
import { ProjectCardPage } from '../ProjectCardPage';

const PROJECT = {
  id: 7,
  domain: 'tours.example',
  niche: 'путешествия',
  geo: 'DE',
  geo_label: 'Германия (DE)',
  service_type: 'seo',
  period_start: '2024-03-01',
  period_end: '2025-09-01',
  publishable: true,
  status: 'classified',
  group: null,
  score: null,
};

const RULES = {
  kinds: [
    { key: 'ahrefs', label: 'Отчёт Ahrefs' },
    { key: 'ai', label: 'Видимость в ИИ' },
  ],
  max_bytes: 2_621_440,
  max_count: 30,
  max_side: 2000,
};

function shot(id: number, kind: string, caption: string) {
  const base = { project_id: 7, mime: 'image/png', width: 640, height: 400, size_bytes: 1000 };
  return { ...base, id, kind, caption, created_at: '2026-10-07T12:00:00Z' };
}

const OVERVIEW = shot(1, 'ahrefs', 'Обзор · Германия (DE)');
const CHATGPT = shot(2, 'ai', 'ChatGPT');
const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

type Reply = { status: number; body: unknown } | (() => { status: number; body: unknown });

interface Sent {
  call: string;
  body: unknown;
}

/** Ответ на «МЕТОД путь»: длиннейший подходящий ключ выигрывает. */
function pick(routes: Record<string, Reply>, method: string, path: string): Response {
  const found = Object.entries(routes)
    .filter(([key]) => key.startsWith(`${method} `) && path.endsWith(key.slice(method.length + 1)))
    .sort(([left], [right]) => right.length - left.length)[0]?.[1];
  const reply = typeof found === 'function' ? found() : found;
  const { status, body } = reply ?? { status: 404, body: { detail: 'нет такого адреса' } };
  return new Response(JSON.stringify(body), { status });
}

function server(routes: Record<string, Reply>): Sent[] {
  const sent: Sent[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const path = url.split('?')[0] ?? '';
      const method = init?.method ?? 'GET';
      if (method !== 'GET') sent.push({ call: `${method} ${url}`, body: init?.body });
      if (path.endsWith('/image')) {
        return new Response(PNG, { status: 200, headers: { 'content-type': 'image/png' } });
      }
      return pick(routes, method, path);
    }),
  );
  return sent;
}

function card(): { status: number; body: unknown } {
  const body = { project: PROJECT, verdict: null, series: [], series_source: 'fixture', brief: {} };
  return { status: 200, body: { ...body, source_mismatch: null } };
}

function routes(shots: () => unknown[]): Record<string, Reply> {
  return {
    'GET /api/projects/7': card(),
    'GET /api/projects/7/charts': { status: 200, body: [] },
    'GET /api/brief-fields': { status: 200, body: { sections: [], fields: [] } },
    'GET /api/screenshot-rules': { status: 200, body: RULES },
    'GET /api/projects/7/screenshots': () => ({ status: 200, body: shots() }),
  };
}

function renderCard(rights: string[]) {
  const inner = globalThis.fetch;
  const me = { email: 'spec@test.local', full_name: 'Специалист', group: 'user', rights };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
      String(input).endsWith('/api/auth/me')
        ? new Response(JSON.stringify(me), { status: 200 })
        : inner(input, init),
    ),
  );
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectCardPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>,
  );
}

async function choose(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await userEvent.upload(input, file, { applyAccept: false });
}

beforeEach(() => {
  rememberToken('токен');
  window.history.pushState({}, '', '/projects/7');
});

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
  window.history.pushState({}, '', '/');
});

describe('скрины на карточке: просмотр', () => {
  it('M61: миниатюры — data:-адресом, подпись с видом словами; без права — только смотреть', async () => {
    server(routes(() => [OVERVIEW, CHATGPT]));

    renderCard(['read']);

    const first = await screen.findByAltText('Отчёт Ahrefs · Обзор · Германия (DE)');
    const second = await screen.findByAltText('Видимость в ИИ · ChatGPT');
    expect(first.getAttribute('src')).toMatch(/^data:image\/png;base64,/);
    expect(second.getAttribute('src')).toMatch(/^data:image\/png;base64,/);
    expect(screen.getByText('Видимость в ИИ · ChatGPT')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Загрузить скрин' })).toBeNull();
    expect(screen.queryByRole('button', { name: /Удалить скрин/ })).toBeNull();
  });

  it('M67: правила не той формы — блок говорит, что скрины не загрузились; бриф на месте', async () => {
    server({ ...routes(() => []), 'GET /api/screenshot-rules': card() });

    renderCard(['read', 'edit_briefs']);

    expect(
      await screen.findByText('Скрины не загрузились: правила скринов пришли не той формы'),
    ).toBeInTheDocument();
    expect(screen.getByText('Бриф для копирайтера')).toBeInTheDocument();
  });
});

describe('скрины на карточке: загрузка и удаление', () => {
  it('M62: вид, подпись и файл уходят одним запросом; список перечитан', async () => {
    let shots = [OVERVIEW];
    const sent = server({
      ...routes(() => shots),
      'POST /api/projects/7/screenshots': () => {
        shots = [OVERVIEW, shot(3, 'ai', 'Perplexity')];
        return { status: 201, body: shots[1] };
      },
    });
    const file = new File([PNG], 'perplexity.png', { type: 'image/png' });

    renderCard(['read', 'edit_briefs']);
    await userEvent.selectOptions(await screen.findByLabelText('Вид скрина'), 'ai');
    await userEvent.type(screen.getByLabelText('Подпись'), 'Perplexity');
    await choose(file);

    expect(await screen.findByAltText('Видимость в ИИ · Perplexity')).toBeInTheDocument();
    expect(sent).toEqual([
      { call: 'POST /api/projects/7/screenshots?kind=ai&caption=Perplexity', body: file },
    ]);
    expect(screen.getByLabelText('Подпись')).toHaveValue('');
  });

  it('M63: отказ сервера — его словами, форма на месте', async () => {
    const detail = 'это не картинка PNG, JPEG или WebP';
    server({
      ...routes(() => []),
      'POST /api/projects/7/screenshots': { status: 415, body: { detail } },
    });

    renderCard(['read', 'edit_briefs']);
    await screen.findByText('Скринов пока нет.');
    await choose(new File(['%PDF-1.7'], 'отчёт.pdf'));

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Загрузить скрин' })).toBeEnabled();
  });

  it('M65: «Удалить» и «Да, удалить» — запрос удаления, скрина в списке нет', async () => {
    let shots = [OVERVIEW, CHATGPT];
    const sent = server({
      ...routes(() => shots),
      'DELETE /api/screenshots/1': () => {
        shots = [CHATGPT];
        return { status: 200, body: { id: 1 } };
      },
    });

    renderCard(['read', 'edit_briefs']);
    const name = 'Удалить скрин «Отчёт Ahrefs · Обзор · Германия (DE)»';
    await userEvent.click(await screen.findByRole('button', { name }));
    await userEvent.click(screen.getByRole('button', { name: 'Да, удалить' }));

    await vi.waitFor(() =>
      expect(screen.queryByText('Отчёт Ahrefs · Обзор · Германия (DE)')).toBeNull(),
    );
    expect(sent.map((item) => item.call)).toEqual(['DELETE /api/screenshots/1']);
    expect(screen.getByText('Видимость в ИИ · ChatGPT')).toBeInTheDocument();
  });
});

describe('удаление проекта называет скрины', () => {
  it('M66: и в окне подтверждения, и в итоге — «скринов: 2»', async () => {
    const view = {
      project_id: 7,
      domain: 'tours.example',
      metric_points: 10,
      verdicts: 1,
      cases: 1,
      files: 1,
      run_items: 2,
      twin_campaigns: 0,
      pack_blocked: false,
      screenshots: 2,
    };
    server({
      ...routes(() => [OVERVIEW, CHATGPT]),
      'GET /api/projects/7/deletion': { status: 200, body: view },
      'DELETE /api/projects/7': { status: 200, body: view },
    });

    renderCard(['read', 'delete_projects']);
    await userEvent.click(await screen.findByRole('button', { name: 'Удалить проект' }));
    const ask = (await screen.findByText(/Удалить tours\.example\?/)).closest('[data-delete]');
    await within(ask as HTMLElement).findByText(/скринов: 2/);
    await userEvent.click(screen.getByRole('button', { name: 'Да, удалить' }));
    const done = (await screen.findByText('Проект tours.example удалён')).closest('[data-deleted]');

    expect(ask).toHaveTextContent('файлов PDF: 1; скринов: 2.');
    expect(done).toHaveTextContent('файлов PDF: 1; скринов: 2.');
  });
});

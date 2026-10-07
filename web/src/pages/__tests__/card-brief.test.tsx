/**
 * Бриф для копирайтера на карточке. Примеры приёмки M28–M32 поставки `brief-form`.
 *
 * Отдельный файл: тесты карточки упираются в предел длины файла. Подменный
 * сервер сличает метод и путь, длиннейший путь выигрывает: правка брифа и
 * карточка делят префикс адреса (урок L186).
 */
import { screen } from '@testing-library/react';
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

const CATALOG = {
  sections: ['Проект', 'Выполненные работы', 'Результаты работы'],
  fields: [
    {
      key: 'site_type',
      label: 'Тип сайта',
      section: 'Проект',
      kind: 'choice',
      choices: [
        { key: 'marketplace', label: 'Маркетплейс' },
        { key: 'saas', label: 'Сервис / SaaS' },
      ],
      column: 'site_type',
      max_len: 60,
    },
    {
      key: 'language_versions',
      label: 'Языковые версии',
      section: 'Проект',
      kind: 'text',
      choices: [],
      column: '',
      max_len: 300,
    },
    {
      key: 'client_request',
      label: 'Запрос клиента на входе',
      section: 'Выполненные работы',
      kind: 'long_text',
      choices: [],
      column: 'client_request',
      max_len: 3000,
    },
    {
      key: 'folder_url',
      label: 'Папка проекта на Google Drive',
      section: 'Результаты работы',
      kind: 'link',
      choices: [],
      column: 'folder_url',
      max_len: 500,
    },
  ],
};

const DRIVE = 'https://drive.google.com/drive/folders/tours';
const SAVED = { site_type: 'marketplace', client_request: 'рост заявок', folder_url: DRIVE };

interface Reply {
  status: number;
  body: unknown;
}

/** Ответы по «МЕТОД путь»; тела правок запоминаются, чтобы проверить, что ушло. */
function server(routes: Record<string, Reply>): { sent: unknown[] } {
  const sent: unknown[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = (typeof input === 'string' ? input : input.toString()).split('?')[0] ?? '';
      const method = init?.method ?? 'GET';
      if (method !== 'GET') sent.push(JSON.parse(String(init?.body ?? 'null')));
      const found = Object.entries(routes)
        .filter(
          ([key]) => key.startsWith(`${method} `) && path.endsWith(key.slice(method.length + 1)),
        )
        .sort(([left], [right]) => right.length - left.length)[0];
      const reply = found?.[1] ?? { status: 404, body: { detail: 'нет такого адреса' } };
      return new Response(JSON.stringify(reply.body), { status: reply.status });
    }),
  );
  return { sent };
}

function card(brief: Record<string, string>, publishable = true): Reply {
  const project = { ...PROJECT, publishable };
  const body = { project, verdict: null, series: [], series_source: 'fixture', brief };
  return { status: 200, body: { ...body, source_mismatch: null } };
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

function routes(brief: Record<string, string>, publishable = true): Record<string, Reply> {
  return {
    'GET /api/projects/7': card(brief, publishable),
    'GET /api/projects/7/charts': { status: 200, body: [] },
    'GET /api/brief-fields': { status: 200, body: CATALOG },
  };
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

describe('бриф на карточке: просмотр', () => {
  it('M28: пункты по разделам, пункт списка — подписью, пустой — «заполняет специалист»', async () => {
    server(routes(SAVED));

    renderCard(['read']);

    expect(await screen.findByText('Маркетплейс')).toBeInTheDocument();
    expect(screen.getByText('Бриф для копирайтера')).toBeInTheDocument();
    expect(screen.getByText('Выполненные работы')).toBeInTheDocument();
    expect(screen.getByText('рост заявок')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: DRIVE })).toHaveAttribute('href', DRIVE);
    // Языковых версий никто не написал — пробел виден, а не пропущен.
    expect(screen.getByText('заполняет специалист')).toBeInTheDocument();
  });

  it('M29: NDA предупреждает копирайтера, публичный проект — говорит, что можно', async () => {
    server(routes({}, false));

    renderCard(['read']);

    expect(
      await screen.findByText(
        'Непубличный проект (NDA): домен и название клиента в тексте кейса не раскрывать.',
      ),
    ).toBeInTheDocument();
  });

  it('M32: без права правки кнопки «Заполнить бриф» нет', async () => {
    server(routes(SAVED));

    renderCard(['read']);

    await screen.findByText('Маркетплейс');
    expect(screen.queryByRole('button', { name: 'Заполнить бриф' })).not.toBeInTheDocument();
  });
});

describe('бриф на карточке: правка', () => {
  it('M30: уходит только изменённое и NDA; карточка показывает сохранённое', async () => {
    const saved = { ...SAVED, client_request: 'рост заявок из органики', site_type: 'saas' };
    const { sent } = server({
      ...routes(SAVED),
      'PATCH /api/projects/7/brief': {
        status: 200,
        body: { project_id: 7, nda: true, fields: saved },
      },
    });

    renderCard(['read', 'edit_briefs']);
    await userEvent.click(await screen.findByRole('button', { name: 'Заполнить бриф' }));
    await userEvent.type(screen.getByLabelText('Запрос клиента на входе'), ' из органики');
    await userEvent.selectOptions(screen.getByLabelText('Тип сайта'), 'saas');
    await userEvent.click(screen.getByLabelText(/Непубличный проект/));
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить бриф' }));

    expect(await screen.findByText('Сервис / SaaS')).toBeInTheDocument();
    expect(sent).toEqual([
      { fields: { client_request: 'рост заявок из органики', site_type: 'saas' }, nda: true },
    ]);
    expect(screen.getByText(/Непубличный проект \(NDA\)/)).toBeInTheDocument();
  });

  it('M31: отказ сервера назван его словами, форма остаётся открытой', async () => {
    const detail = 'Папка проекта на Google Drive: нужна ссылка https://drive.google.com/…';
    server({
      ...routes(SAVED),
      'PATCH /api/projects/7/brief': { status: 422, body: { detail } },
    });

    renderCard(['read', 'edit_briefs']);
    await userEvent.click(await screen.findByRole('button', { name: 'Заполнить бриф' }));
    const link = screen.getByLabelText('Папка проекта на Google Drive');
    await userEvent.clear(link);
    await userEvent.type(link, 'https://yadi.sk/d/tours');
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить бриф' }));

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Сохранить бриф' })).toBeInTheDocument();
  });
});

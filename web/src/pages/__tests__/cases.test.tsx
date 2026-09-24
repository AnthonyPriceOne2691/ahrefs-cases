/**
 * Экран «Кейсы». Примеры приёмки E1–E8.
 *
 * Проверяется то, ради чего экран есть: видно ли, что собрано, видно ли, что
 * из этого нельзя публиковать под именем, и уходит ли файл с токеном — прямая
 * ссылка вернула бы `401`, и это единственная причина не делать её ссылкой.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { forgetToken, rememberToken } from '../../api/client';
import { AuthProvider } from '../../auth/AuthProvider';
import { renderApp } from '../../test/render';
import { CasesPage } from '../CasesPage';

interface Reply {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}

function caseRow(id: number, extra: Record<string, unknown> = {}) {
  return {
    id,
    project_id: id,
    domain: `site-${id}.example`,
    version: 1,
    anonymized: false,
    status: 'built',
    created_at: '2026-09-11T10:00:00Z',
    filename: `site-${id}.example — Кейс.pdf`,
    checksum: 'abc',
    ...extra,
  };
}

const PACK = {
  exists: true,
  filename: 'кейсы-2026-09-11.zip',
  size_bytes: 3_145_728,
  built_at: '2026-09-11T10:30:00Z',
  note: 'архив собран последней сборкой кейсов',
};

interface Call {
  url: string;
  headers: Record<string, string>;
}

/** Запросы экрана. Путь сравнивается целиком: `/api/cases` и `/api/cases/pack`
 *  различаются только хвостом, и совпадение по вхождению спутало бы их. */
function server(routes: Record<string, Reply>): { calls: Call[] } {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      calls.push({ url, headers: (init?.headers ?? {}) as Record<string, string> });
      const path = (url.split('?')[0] ?? url).replace('http://localhost', '');
      const reply = routes[path] ?? { status: 404, body: { detail: 'нет пути' } };
      const body = reply.body instanceof Blob ? reply.body : JSON.stringify(reply.body);
      return new Response(body, { status: reply.status, headers: reply.headers });
    }),
  );
  return { calls };
}

function me(rights: string[]): Reply {
  return {
    status: 200,
    body: { email: 'clerk@test.local', full_name: 'Сотрудник', group: 'user', rights },
  };
}

function show() {
  return renderApp(
    <AuthProvider>
      <BrowserRouter>
        <CasesPage />
      </BrowserRouter>
    </AuthProvider>,
  );
}

let saved: { name: string; blob: Blob } | null = null;

beforeEach(() => {
  rememberToken('токен');
  saved = null;
  // jsdom не умеет ни `createObjectURL`, ни настоящее скачивание: подменяем обе
  // половины и смотрим, что именно ушло бы в файл.
  //
  // Подмена — наследник, а не объект `{ ...URL }`: разворот класса теряет сам
  // конструктор, а маршрутизатор собирает адрес через `new URL`. Листалка и
  // тумблер версий роняли его вне теста — тесты зеленели, прогон выходил с 1.
  vi.stubGlobal(
    'URL',
    class extends URL {
      static createObjectURL = vi.fn(() => 'blob:кейс');
      static revokeObjectURL = vi.fn();
    },
  );
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved = { name: this.download, blob: new Blob() };
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  forgetToken();
});

describe('библиотека кейсов', () => {
  it('E1 и E2: строки с версией и меткой публикации', async () => {
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': {
        status: 200,
        body: [caseRow(1), caseRow(2, { anonymized: true, version: 2 })],
      },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByText('site-1.example')).toBeInTheDocument();
    expect(screen.getByText('можно публиковать')).toBeInTheDocument();
    // Анонимизированный кейс помечен следствием: публиковать под именем нельзя.
    expect(screen.getByText('домен скрыт')).toBeInTheDocument();
  });

  it('E3: у кейса без файла скачивания нет, и сказано почему', async () => {
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1, { filename: null, checksum: null })] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByText(/файла нет/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Скачать PDF' })).not.toBeInTheDocument();
  });

  it('E4: кейс уходит запросом с токеном и сохраняется под именем сервера', async () => {
    const { calls } = server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1)] },
      '/api/cases/pack': { status: 200, body: PACK },
      '/api/cases/1/download': {
        status: 200,
        body: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
        headers: {
          'content-disposition': "attachment; filename*=utf-8''%D0%9A%D0%B5%D0%B9%D1%81.pdf",
        },
      },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Скачать PDF' }));

    await waitFor(() => expect(saved).not.toBeNull());
    // Имя приходит процентами и раскодируется: иначе человек нашёл бы в папке
    // загрузок файл с именем из процентов.
    expect(saved?.name).toBe('Кейс.pdf');
    const download = calls.find((call) => call.url.includes('/api/cases/1/download'));
    expect(download?.headers.Authorization).toBe('Bearer токен');
  });

  it('E5: пустая библиотека объясняет, чем это чинится', async () => {
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByText(/Кейсов ещё нет/)).toBeInTheDocument();
  });

  it('E6: отказ сервера показан его же словами', async () => {
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 403, body: { detail: 'нужно право read' } },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByText('нужно право read')).toBeInTheDocument();
  });

  it('E9: тумблер просит у сервера все версии, а не фильтрует страницу', async () => {
    const { calls } = server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1)] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();
    await userEvent.click(await screen.findByLabelText('показать все версии'));

    // Именно запросом: страница отдаёт двадцать строк, и фильтрация уже
    // полученного показала бы историю двух проектов вместо истории всех.
    await waitFor(() =>
      expect(calls.some((call) => call.url.includes('all_versions=true'))).toBe(true),
    );
  });
});

describe('листание библиотеки', () => {
  it('листает по двадцать строк и не теряет тумблер версий', async () => {
    // Библиотека росла до полусотни и обрывалась молча: сервер отдавал первые
    // строки, а человек видел в них всю выдачу. `offset` у сервера был с
    // самого начала — фронт его не спрашивал.
    const full = Array.from({ length: 20 }, (_, index) => caseRow(index + 1));
    const { calls } = server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: full },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();
    await screen.findByText('Страница 1');
    expect(screen.getByRole('button', { name: 'Назад' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Вперёд' }));

    expect(await screen.findByText('Страница 2')).toBeInTheDocument();
    await waitFor(() => expect(calls.some((call) => call.url.includes('offset=20'))).toBe(true));

    // Тумблер версий меняет длину списка, поэтому возвращает на первую
    // страницу: третьей страницы нового списка может не быть вовсе.
    await userEvent.click(screen.getByLabelText('показать все версии'));
    expect(await screen.findByText('Страница 1')).toBeInTheDocument();
  });
});

describe('пачка', () => {
  it('E7: без права `run` кнопки пересборки нет', async () => {
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1)] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByRole('button', { name: 'Скачать ZIP' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Пересобрать кейсы' })).not.toBeInTheDocument();
  });

  it('E8: пересборка называет номер прогона и путь в журнал', async () => {
    server({
      '/api/auth/me': me(['read', 'run']),
      '/api/cases': { status: 200, body: [caseRow(1)] },
      '/api/cases/pack': { status: 200, body: PACK },
      '/api/runs/cases': { status: 202, body: { run_id: 17, queued_as: 'redis' } },
    });

    show();
    await userEvent.click(await screen.findByRole('button', { name: 'Пересобрать кейсы' }));

    expect(await screen.findByText(/№17/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /журнале прогонов/ })).toHaveAttribute('href', '/runs');
  });

  it('пачки нет — сказано словами сервера, а скачивать нечего', async () => {
    server({
      '/api/auth/me': me(['read', 'run']),
      '/api/cases': { status: 200, body: [] },
      '/api/cases/pack': {
        status: 200,
        body: {
          ...PACK,
          exists: false,
          filename: null,
          size_bytes: null,
          built_at: null,
          note: 'пачка ещё не собиралась',
        },
      },
    });

    show();

    expect(await screen.findByText('пачка ещё не собиралась')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Скачать ZIP' })).toBeDisabled();
  });
});

describe('статусы кейсов', () => {
  it('E10: статус кейса показан по-русски', async () => {
    // «BUILT» посреди русского экрана — значение перечисления, а не состояние.
    server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1), caseRow(2, { status: 'published' })] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();

    expect(await screen.findByText('собран')).toBeInTheDocument();
    expect(screen.getByText('опубликован')).toBeInTheDocument();
    expect(screen.queryByText('built')).not.toBeInTheDocument();
  });
});

describe('состояние библиотеки переживает обновление', () => {
  it('страница и тумблер версий берутся из адреса', async () => {
    window.history.replaceState(
      {},
      '',
      '/cases?page=1&%D0%B2%D0%B5%D1%80%D1%81%D0%B8%D0%B8=%D0%B4%D0%B0',
    );
    const { calls } = server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: [caseRow(1)] },
      '/api/cases/pack': { status: 200, body: PACK },
    });

    show();
    await screen.findByText('Страница 2');

    const asked = calls.find((call) => call.url.includes('/api/cases?'));
    expect(asked?.url).toContain('offset=20');
    expect(asked?.url).toContain('all_versions=true');
  });
});

describe('выбор кейсов для скачивания', () => {
  function library(rows: unknown[]) {
    return server({
      '/api/auth/me': me(['read']),
      '/api/cases': { status: 200, body: rows },
      '/api/cases/pack': { status: 200, body: PACK },
      '/api/cases/selection/download': {
        status: 200,
        body: new Blob(['PK'], { type: 'application/zip' }),
        // Кириллица в заголовке уезжает формой RFC 5987 — именно так её шлёт
        // Starlette, и именно её разбирает `nameFromHeaders`. Сырое
        // `filename="выборка…"` в заголовок не помещается вовсе: jsdom требует
        // ByteString и падает на первом же символе за пределами latin-1.
        headers: {
          'content-disposition':
            "attachment; filename*=utf-8''%D0%B2%D1%8B%D0%B1%D0%BE%D1%80%D0%BA%D0%B0-%D0%BA%D0%B5%D0%B9%D1%81%D0%BE%D0%B2.zip",
        },
      },
      '/api/cases/1/download': {
        status: 200,
        body: new Blob(['%PDF-'], { type: 'application/pdf' }),
        headers: {
          'content-disposition': "attachment; filename*=utf-8''%D0%BE%D0%B4%D0%B8%D0%BD.pdf",
        },
      },
    });
  }

  it('несколько выбранных уезжают одним архивом', async () => {
    const net = library([caseRow(1), caseRow(2), caseRow(3)]);
    show();
    await screen.findByText('site-1.example');

    await userEvent.click(screen.getByLabelText('выбрать кейс site-1.example'));
    await userEvent.click(screen.getByLabelText('выбрать кейс site-3.example'));
    await userEvent.click(screen.getByRole('button', { name: /Скачать выбранные \(2\)/ }));

    await waitFor(() => expect(saved?.name).toBe('выборка-кейсов.zip'));
    const asked = net.calls.map((call) => call.url).find((url) => url.includes('selection'));
    expect(asked).toContain('ids=1');
    expect(asked).toContain('ids=3');
    expect(asked).not.toContain('ids=2');
  });

  it('один выбранный — это PDF, а не архив из одного файла', async () => {
    library([caseRow(1), caseRow(2)]);
    show();
    await screen.findByText('site-1.example');

    await userEvent.click(screen.getByLabelText('выбрать кейс site-1.example'));
    await userEvent.click(screen.getByRole('button', { name: 'Скачать выбранный PDF' }));

    await waitFor(() => expect(saved?.name).toBe('один.pdf'));
  });

  it('«выбрать всё» берёт только то, у чего есть файл', async () => {
    library([caseRow(1), caseRow(2, { filename: null, checksum: null }), caseRow(3)]);
    show();
    await screen.findByText('site-1.example');

    await userEvent.click(screen.getByLabelText('выбрать все кейсы на странице'));

    expect(screen.getByRole('button', { name: /Скачать выбранные \(2\)/ })).toBeInTheDocument();
    expect(screen.getByLabelText('выбрать кейс site-2.example')).toBeDisabled();
  });

  it('пока ничего не выбрано, кнопок выбора нет', async () => {
    library([caseRow(1)]);
    show();
    await screen.findByText('site-1.example');

    expect(screen.queryByRole('button', { name: /Скачать выбранные/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Снять выделение' })).not.toBeInTheDocument();
  });

  it('место под панель занято и до выбора — таблица не прыгает', async () => {
    library([caseRow(1), caseRow(2)]);
    show();
    await screen.findByText('site-1.example');

    // Пустой `null` убирал панель из потока, и первая же отметка сдвигала вниз
    // всю таблицу: строка уезжала из-под курсора, а следующую человек отмечал
    // вслепую. Место занято всегда — меняется только содержимое.
    const before = document.querySelector('[data-selection-bar]');
    expect(before).not.toBeNull();
    expect(before?.getAttribute('data-selection-bar')).toBe('empty');

    await userEvent.click(screen.getByLabelText('выбрать кейс site-1.example'));

    const after = document.querySelector('[data-selection-bar]');
    expect(after?.getAttribute('data-selection-bar')).toBe('filled');
    expect(document.querySelectorAll('[data-selection-bar]')).toHaveLength(1);
  });
});

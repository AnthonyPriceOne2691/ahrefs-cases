/**
 * Четыре исхода запроса. Примеры приёмки E7, E8, E9.
 *
 * Различаются не ради аккуратности: `401` — войти заново, `403` — попросить
 * право, `503` — сказать инженеру про настройку. Слитые в «ошибку», они
 * оставляют человека без следующего шага (уроки L32, L34).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, forgetToken, rememberToken, request } from '../client';

function answer(status: number, body: unknown): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  forgetToken();
});

describe('клиент API', () => {
  it('кладёт токен в заголовок, когда он есть', async () => {
    const seen: RequestInit[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        seen.push(init ?? {});
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );
    rememberToken('токен-для-теста');

    await request('/api/projects');

    const headers = seen[0]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer токен-для-теста');
  });

  it('E7: 401 отличается от прочих отказов', async () => {
    answer(401, { detail: 'нужен действующий токен' });

    await expect(request('/api/projects')).rejects.toMatchObject({ needsLogin: true });
  });

  it('E8: 403 называет недостающее право', async () => {
    answer(403, { detail: 'нет права edit_thresholds: группа user' });

    await expect(request('/api/rulesets')).rejects.toThrow(/edit_thresholds/);
  });

  it('E9: 503 объясняет, что сервис не настроен', async () => {
    answer(503, { detail: 'в базе нет активной версии порогов' });

    const failure = await request('/api/projects').catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).misconfigured).toBe(true);
    expect((failure as ApiError).message).toContain('активной версии порогов');
  });

  it('не теряет код ответа, если тело не разобралось', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<html>шлюз</html>', { status: 502 })),
    );

    await expect(request('/api/projects')).rejects.toThrow(/502/);
  });
});

/**
 * Клиент API: токен в заголовке и четыре разных исхода запроса.
 *
 * Исходы различаются не ради аккуратности, а потому что действия человека
 * разные: `401` — войти заново, `403` — попросить право, `503` — сказать
 * инженеру, что сервис не настроен. Сведённые в одно «что-то пошло не так»,
 * они оставляют человека без следующего шага.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  /** Нужен вход: токена нет, он протух или пользователя выключили. */
  get needsLogin(): boolean {
    return this.status === 401;
  }

  /** Не хватает права. Текст сервера называет какого именно. */
  get forbidden(): boolean {
    return this.status === 403;
  }

  /** Сервис не настроен (нет активной версии порогов, нет секрета подписи). */
  get misconfigured(): boolean {
    return this.status === 503;
  }
}

export const TOKEN_KEY = 'ahrefs-cases.token';

export function storedToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function rememberToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function forgetToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /**
   * Тело уходит как есть, без JSON: так отправляется файл списка.
   *
   * `Content-Type` при этом не подставляется вовсе — его ставит браузер по типу
   * файла. Подставить свой значило бы соврать серверу о содержимом.
   */
  raw?: Blob;
  /** Запрос без токена — только вход. */
  anonymous?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (!options.raw) headers['Content-Type'] = 'application/json';
  const token = storedToken();
  if (token && !options.anonymous) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers,
    body: options.raw ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
  });

  if (response.status === 204) return undefined as T;
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return (await response.json()) as T;
}

/** Файл, полученный с сервера: содержимое и имя, под которым его сохранять. */
export interface DownloadedFile {
  blob: Blob;
  filename: string;
}

/**
 * Скачать файл тем же токеном, что и остальные запросы.
 *
 * Прямая ссылка `<a href="/api/cases/1/download">` здесь не работает: браузер
 * отправит её без заголовка `Authorization` — токен у нас не в куке — и человек
 * получит `401` вместо кейса. Поэтому файл берётся запросом, а сохраняется уже
 * из памяти.
 */
export async function download(path: string, fallbackName: string): Promise<DownloadedFile> {
  const headers: Record<string, string> = {};
  const token = storedToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(path, { headers });
  if (!response.ok) throw new ApiError(response.status, await readDetail(response));
  return { blob: await response.blob(), filename: nameFromHeaders(response) ?? fallbackName };
}

/**
 * Имя файла из `Content-Disposition`.
 *
 * Имена у нас кириллические («example.com — Кейс.pdf»), и сервер отдаёт их
 * формой `filename*=utf-8''…` с процентами. Не раскодировав, человек сохранил
 * бы файл с именем из процентов — и не узнал бы его в папке загрузок.
 */
function nameFromHeaders(response: Response): string | null {
  const header = response.headers.get('content-disposition') ?? '';
  const encoded = /filename\*=utf-8''([^;]+)/i.exec(header);
  if (encoded?.[1]) return decodeURIComponent(encoded[1]);
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain?.[1] ?? null;
}

async function readDetail(response: Response): Promise<string> {
  // Тело читается в try: сервер мог ответить не JSON (прокси, шлюз), и потерять
  // код ответа из-за этого нельзя — именно он говорит, что делать дальше.
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // разбор не удался — ниже вернётся общий текст с кодом
  }
  return `сервер ответил ${response.status}`;
}

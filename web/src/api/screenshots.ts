/**
 * Скрины брифа: правила, список, загрузка, картинка, удаление.
 *
 * Картинка берётся запросом с токеном и показывается `data:`-адресом: ссылку
 * `<img src="/api/…">` браузер отправит без заголовка `Authorization`, а `blob:`
 * не пускает политика безопасности сайта (`img-src 'self' data:` в nginx).
 *
 * Правила и список проверяются формой при получении (урок L242): чужой ответ,
 * принятый за список, ронял бы карточку целиком, а не один блок скринов.
 */
import { downloadBytes, request } from './client';
import type { ScreenshotRules, ScreenshotView } from './types';

export async function fetchScreenshotRules(): Promise<ScreenshotRules> {
  const rules = await request<Partial<ScreenshotRules> | null>('/api/screenshot-rules');
  const { kinds, max_bytes: maxBytes, max_count: maxCount, max_side: maxSide } = rules ?? {};
  if (
    !Array.isArray(kinds) ||
    typeof maxBytes !== 'number' ||
    typeof maxCount !== 'number' ||
    typeof maxSide !== 'number'
  ) {
    throw new Error('правила скринов пришли не той формы');
  }
  return { kinds, max_bytes: maxBytes, max_count: maxCount, max_side: maxSide };
}

export async function fetchScreenshots(projectId: number): Promise<ScreenshotView[]> {
  const rows = await request<unknown>(`/api/projects/${projectId}/screenshots`);
  if (!Array.isArray(rows)) throw new Error('список скринов пришёл не той формы');
  return rows as ScreenshotView[];
}

/** Тело — сама картинка, как файл списка: тип по содержимому определит сервер. */
export function uploadScreenshot(
  projectId: number,
  image: Blob,
  kind: string,
  caption: string,
): Promise<ScreenshotView> {
  const query = new URLSearchParams({ kind, caption });
  return request<ScreenshotView>(`/api/projects/${projectId}/screenshots?${query.toString()}`, {
    method: 'POST',
    raw: image,
  });
}

export function deleteScreenshot(screenshotId: number): Promise<unknown> {
  return request<unknown>(`/api/screenshots/${screenshotId}`, { method: 'DELETE' });
}

export async function fetchScreenshotImage(screenshotId: number): Promise<string> {
  const { bytes, type } = await downloadBytes(`/api/screenshots/${screenshotId}/image`);
  return dataUrl(new Uint8Array(bytes), type);
}

/** Сколько байт переводить в строку за раз: `String.fromCharCode` с сотнями тысяч
 *  аргументов переполняет стек, а скрин бывает до 2,5 МБ. */
const CHUNK = 0x8000;

/** `data:`-адрес картинки из её байтов (почему не через `FileReader` — `downloadBytes`). */
function dataUrl(bytes: Uint8Array, type: string): string {
  let binary = '';
  for (let start = 0; start < bytes.length; start += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(start, start + CHUNK));
  }
  return `data:${type || 'application/octet-stream'};base64,${btoa(binary)}`;
}

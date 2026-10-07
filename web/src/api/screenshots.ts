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
import { download, request } from './client';
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
  const { blob } = await download(`/api/screenshots/${screenshotId}/image`, 'скрин');
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error('картинку скрина не прочитать'));
    reader.readAsDataURL(blob);
  });
}

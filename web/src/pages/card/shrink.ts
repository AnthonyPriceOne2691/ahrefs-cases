/**
 * Скрин больше предела сервера ужимается здесь, до отправки.
 *
 * Отправить большой и ждать отказа нельзя: сервер закрывает соединение, не
 * дочитав тело, и прокси отвечает человеку своей ошибкой вместо «больше 2,5 МБ»
 * (так было с файлом списка — `intake/SourceForm`). Ужатие — как у сервера:
 * длинная сторона до его предела, JPEG; прозрачное — на белом, иначе JPEG
 * зальёт его чёрным. Оба числа — из правил сервера, своих копий здесь нет.
 */
import { megabytes } from '../format';

const QUALITY = 0.88;

/** Пределы из правил сервера (`/api/screenshot-rules`). */
export interface Limits {
  maxBytes: number;
  maxSide: number;
}

export type Resize = (image: Blob, maxSide: number) => Promise<Blob>;

/** Скрин не влез в предел и после ужатия: отправлять бесполезно. */
export class TooBigError extends Error {}

export async function fitForUpload(
  image: Blob,
  { maxBytes, maxSide }: Limits,
  resize: Resize = inBrowser,
): Promise<Blob> {
  if (image.size <= maxBytes) return image;
  const smaller = await resize(image, maxSide);
  if (smaller.size > maxBytes) {
    throw new TooBigError(
      `скрин больше ${megabytes(maxBytes)} МБ даже после ужатия — обрежьте лишнее и загрузите снова`,
    );
  }
  return smaller;
}

async function inBrowser(image: Blob, maxSide: number): Promise<Blob> {
  const bitmap = await createImageBitmap(image).catch((cause: unknown) => {
    throw new Error('файл не открылся как картинка — нужен PNG, JPEG или WebP', { cause });
  });
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const context = canvas.getContext('2d');
  if (!context) throw new Error('браузер не дал холст, чтобы ужать скрин');
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const encoded = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob(resolve, 'image/jpeg', QUALITY);
  });
  if (!encoded) throw new Error('браузер не смог ужать скрин');
  return encoded;
}

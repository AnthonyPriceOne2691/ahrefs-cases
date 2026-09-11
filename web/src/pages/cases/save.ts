/**
 * Сохранение полученного файла на диск человека.
 *
 * Ссылка живёт ровно один клик и отзывается сразу: `createObjectURL` держит
 * blob в памяти вкладки до конца её жизни, и без `revoke` экран, открытый на
 * день, накопил бы все скачанные пачки.
 */
import type { DownloadedFile } from '../../api/client';

export function saveFile({ blob, filename }: DownloadedFile): void {
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.rel = 'noopener';
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

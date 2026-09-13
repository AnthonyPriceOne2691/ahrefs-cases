/**
 * Как называются статусы прогонов и кейсов. Одно место на весь интерфейс.
 *
 * Раньше каждый экран печатал сырое значение перечисления: «BUILT» в таблице
 * кейсов, «done» в журнале прогонов, «running» в строке загрузки — латиница
 * посреди русского экрана. Человек читает не enum, а исход.
 *
 * Устроено как [`groups.ts`](./groups.ts) и по той же причине: словарь, живущий
 * в двух местах, расходится молча — в предпросмотре порогов «good → poor» уже
 * один раз уехало мимо русского экрана.
 */

/** Исходы прогона. Их шесть, и «частично» — не то же, что «готово». */
export const RUN_STATUS_LABELS: Record<string, string> = {
  queued: 'в очереди',
  running: 'идёт',
  done: 'готов',
  partial: 'частично',
  failed: 'упал',
  cancelled: 'отменён',
  // Прогон, не прошедший проверку квоты, не «упал»: он **не начинался**, и
  // units не потрачены. Разница решает, что делать человеку — чинить или ждать.
  rejected: 'отклонён по квоте',
};

/** Состояния кейса: собран, опубликован, черновик. */
export const CASE_STATUS_LABELS: Record<string, string> = {
  draft: 'черновик',
  built: 'собран',
  published: 'опубликован',
};

/** Незнакомое значение показываем как есть: выдумывать ему слово опаснее, чем
 *  показать сырое — по нему хотя бы понятно, что сервис знает больше экрана. */
function word(labels: Record<string, string>, status: string): string {
  return labels[status] ?? status;
}

export function runWord(status: string): string {
  return word(RUN_STATUS_LABELS, status);
}

export function caseWord(status: string): string {
  return word(CASE_STATUS_LABELS, status);
}

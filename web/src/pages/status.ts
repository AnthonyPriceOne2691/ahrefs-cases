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

/** Исходы проекта в прогоне. Пропуск — штатный исход, а не ошибка, и видов
 *  у него четыре: по каждому человек делает разное. */
export const RUN_ITEM_LABELS: Record<string, string> = {
  ok: 'собран',
  skipped_no_data: 'пропущен: нет данных',
  skipped_invalid: 'пропущен: строка не принята',
  skipped_quota: 'пропущен: не хватило units',
  skipped_aborted: 'не выполнен: прогон остановлен',
  failed: 'упал',
  // Сборка кейсов: Ahrefs она не спрашивает, и её исходы — про кейс, а не про
  // данные. Собранный кейс — тот же `ok`, «собран».
  case_not_eligible: 'не положен по группе',
  case_insufficient_data: 'данных не хватило',
  case_no_verdict: 'вердикта этой версии нет',
  case_verdict_mismatch: 'вердикт не про эти данные',
  case_blocked: 'не отдан: контент-запрет',
};

/** Незнакомое значение показываем как есть: выдумывать ему слово опаснее, чем
 *  показать сырое — по нему хотя бы понятно, что сервис знает больше экрана. */
function word(labels: Record<string, string>, status: string): string {
  return labels[status] ?? status;
}

/** Ступень прогона (B6): без неё сборка кейсов читалась как сбор «0 из 18». */
export const RUN_STAGE_LABELS: Record<string, string> = {
  stage1: 'шаг 1',
  stage2: 'шаг 2',
  case_data: 'данные под кейс',
  cases: 'сборка кейсов',
  cycle: 'цикл по файлу',
};

export function stageWord(stage: string): string {
  // Пусто — прогон старше поля: ступень неизвестна, и придумывать её нельзя.
  return stage ? word(RUN_STAGE_LABELS, stage) : '';
}

export function runWord(status: string): string {
  return word(RUN_STATUS_LABELS, status);
}

export function caseWord(status: string): string {
  return word(CASE_STATUS_LABELS, status);
}

export function fateWord(outcome: string): string {
  return word(RUN_ITEM_LABELS, outcome);
}

/**
 * Почему units прогона — не расход. `null` — живой прогон, пометка не нужна.
 *
 * Живой ли прогон, решает сервер (`live`, тем же правилом, что «потрачено»);
 * здесь только слово по записанному режиму. Без пометки у fixture-прогона
 * «смета → факт» читалась как настоящий расход (Z38).
 */
export function unitsNote(run: { live: boolean; mode: string }): string | null {
  if (run.live) return null;
  if (!run.mode) return 'режим не записан — units не считаются расходом';
  return `условные units: прогон без живого ключа (${run.mode})`;
}

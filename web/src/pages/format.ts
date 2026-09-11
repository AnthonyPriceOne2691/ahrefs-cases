/**
 * Числа и даты экранов. Форматирование одно на все.
 *
 * Дробных знаков нет: метрики — визиты, ключи и домены, и «4 189,936» читается
 * как точность, которой у этих оценок нет.
 */
export function num(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

/**
 * Рост в процентах. `null` — рост от нулевой базы, и это не «100 %».
 *
 * Сервер присылает `null` намеренно: рост с нуля до сорока визитов формально
 * бесконечен, а по сути ничего не значит. Подменять его числом здесь значило бы
 * вернуть ту самую ложь, от которой отказались в классификации.
 */
export function growth(pct: number | null, absolute: number): string {
  if (pct === null) return absolute > 0 ? 'с нуля' : '—';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`;
}

/**
 * Период работ месяцами: «03.2024 — 09.2025».
 *
 * День старта в расчётах не участвует (точки А и Б усредняются по месяцам), а в
 * таблице занимает место, которое нужнее домену. Одна функция на список и на
 * карточку: две копии разошлись бы форматом, и один и тот же проект выглядел бы
 * по-разному на соседних экранах.
 */
export function months(from: string, to: string): string {
  const short = (iso: string) => iso.slice(0, 7).split('-').reverse().join('.');
  return `${short(from)} — ${short(to)}`;
}

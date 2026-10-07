/**
 * Бриф на экране: подпись значения, разделы шаблона и что изменилось в форме.
 *
 * Логика вне компонентов: её проверяют без отрисовки, а форма и просмотр берут
 * одни и те же правила (урок L97).
 */
import type { BriefCatalog, BriefField } from '../../api/types';

/** Что видит копирайтер у пустого пункта — то же слово, что на листе PDF. */
export const EMPTY = 'заполняет специалист';

/** Подпись записанного значения: у пункта списка — его название, ключ без пункта — как есть. */
export function shown(field: BriefField, value: string | undefined): string {
  if (!value) return EMPTY;
  return field.choices.find((choice) => choice.key === value)?.label ?? value;
}

/** Поля по разделам шаблона — в его порядке; пустой раздел не показывается. */
export function bySection(catalog: BriefCatalog): [string, BriefField[]][] {
  return catalog.sections
    .map((section): [string, BriefField[]] => [
      section,
      catalog.fields.filter((field) => field.section === section),
    ])
    .filter(([, fields]) => fields.length > 0);
}

/** Только изменённые поля: сервер пишет названное, а пустая строка очищает. */
export function changes(
  saved: Record<string, string>,
  draft: Record<string, string>,
): Record<string, string> {
  const changed: Record<string, string> = {};
  for (const key of new Set([...Object.keys(saved), ...Object.keys(draft)])) {
    const before = saved[key] ?? '';
    const after = (draft[key] ?? '').trim();
    if (before !== after) changed[key] = after;
  }
  return changed;
}

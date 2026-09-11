/**
 * Разделы сервиса и права, которые они требуют.
 *
 * Одно место, где решается «кому что видно». Разъехавшись по компонентам, это
 * правило перестанет совпадать с серверным — и человек увидит кнопку, ведущую
 * к `403`, то есть интерфейс, который врёт.
 *
 * Скрытая кнопка при этом **не защита**: проверки на роутерах стоят и остаются.
 */

export interface NavSection {
  path: string;
  label: string;
  /** Право, без которого раздел не показывается. `null` — виден всем вошедшим. */
  right: string | null;
}

export const NAV_SECTIONS: readonly NavSection[] = [
  // «Загрузка» первой: с неё начинается работа, и порядок меню — это порядок
  // сценария, а не алфавит.
  { path: '/intake', label: 'Загрузка', right: 'run' },
  { path: '/projects', label: 'Проекты', right: 'read' },
  { path: '/cases', label: 'Кейсы', right: 'read' },
  { path: '/runs', label: 'Прогоны', right: 'read' },
  { path: '/usage', label: 'Расход units', right: 'read' },
  { path: '/thresholds', label: 'Пороги', right: 'edit_thresholds' },
  { path: '/users', label: 'Люди', right: 'manage_users' },
];

export function visibleSections(rights: readonly string[]): NavSection[] {
  return NAV_SECTIONS.filter((section) => section.right === null || rights.includes(section.right));
}

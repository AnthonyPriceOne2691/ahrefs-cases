/**
 * Навигация по правам. Примеры приёмки E4, E5, E6.
 *
 * Меню строится по **правам**, а не по названию группы: с Ф5.5 право выдаётся
 * и лично, поверх группы, и меню по группе не показало бы раздел тому, кому
 * право выдали точечно (урок L59).
 */
import { describe, expect, it } from 'vitest';

import { visibleSections } from '../nav';

const labels = (rights: string[]) => visibleSections(rights).map((section) => section.label);

describe('разделы по правам', () => {
  it('E4: обычный пользователь не видит порогов и людей', () => {
    const seen = labels(['read', 'run']);

    expect(seen).toContain('Проекты');
    expect(seen).not.toContain('Пороги');
    expect(seen).not.toContain('Люди');
  });

  it('E5: администратор видит оба раздела', () => {
    const seen = labels(['read', 'run', 'edit_thresholds', 'manage_users']);

    expect(seen).toContain('Пороги');
    expect(seen).toContain('Люди');
  });

  it('E6: право, выданное лично, открывает раздел без смены группы', () => {
    // Ровно тот случай, ради которого меню строится по правам: группа у
    // человека прежняя, право выдано точечно.
    expect(labels(['read', 'manage_users'])).toContain('Люди');
    expect(labels(['read', 'manage_users'])).not.toContain('Пороги');
  });
});

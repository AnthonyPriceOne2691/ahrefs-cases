/**
 * Право человека и **откуда оно взялось**.
 *
 * Главная сложность экрана: «админ» в строке не означает, что человеку можно
 * всё, что даёт группа админа. Право могли отобрать лично, и наоборот —
 * выдать поверх группы. Показать только итог значит спрятать причину, показать
 * только личные — спрятать сам доступ.
 */
export type Origin = 'группа' | 'выдано лично' | 'отобрано лично';

export interface RightState {
  right: string;
  allowed: boolean;
  origin: Origin;
}

/** Русские названия прав. Право — это строка в API; человеку нужна работа,
 *  которую она открывает. */
const LABELS: Record<string, string> = {
  read: 'смотреть данные',
  run: 'запускать прогоны',
  edit_thresholds: 'править пороги',
  manage_users: 'заводить людей',
  change_technical_settings: 'технические настройки',
};

export function rightLabel(right: string): string {
  return LABELS[right] ?? right;
}

/**
 * Состояние каждого права человека: даёт ли группа, решили ли лично.
 *
 * `fromGroup` — набор его группы из справочника сервера. Права, которых группа
 * не даёт и лично не выдавали, в ответе не возвращаются вовсе: строка про
 * «нельзя, как у всех в группе» никому не нужна.
 */
export function rightStates(
  personal: Record<string, boolean>,
  fromGroup: readonly string[],
): RightState[] {
  const states: RightState[] = [];
  for (const right of fromGroup) {
    if (personal[right] === false) {
      states.push({ right, allowed: false, origin: 'отобрано лично' });
    } else {
      states.push({ right, allowed: true, origin: 'группа' });
    }
  }
  for (const [right, allowed] of Object.entries(personal)) {
    if (allowed && !fromGroup.includes(right)) {
      states.push({ right, allowed: true, origin: 'выдано лично' });
    }
  }
  return states;
}

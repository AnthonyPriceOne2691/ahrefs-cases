/**
 * Раскрытие одного из списка: нажал — открылось, нажал ещё раз — свернулось.
 *
 * Поведение придумано на экране людей (Ф5.5) и владельцем названо образцом для
 * остальных экранов. Оно живёт здесь, а не копией в каждом: три случая нажатия
 * различаются неочевидно, и второй экземпляр разошёлся бы с первым на третьем
 * случае — том самом, который и делает раскрытие спокойным.
 *
 * Источник правды — состояние компонента, адрес получает копию. Наоборот было
 * бы стройнее, но панель едет вниз по таймеру, и её открытие зависело бы от
 * того, успел ли маршрутизатор довезти новый адрес.
 */
import { useRef, useState } from 'react';

import { useScreenState } from './screenState';

/** Столько едет панель. Тем же числом задаётся пауза между «свернуть чужое» и
 *  «открыть своё»: иначе одно накладывается на другое. */
export const FOLD_MS = 220;

export interface FoldedChoice {
  /** Что выбрано сейчас. Панель этого элемента раскрыта. */
  chosen: string | null;
  /** Чьё содержимое показывать. Отстаёт от `chosen` на время сворачивания:
   *  убери содержимое сразу — и сворачивать будет нечего, вместо анимации
   *  получится мгновенное исчезновение. */
  shown: string | null;
  /** Нажатие на элемент. */
  choose: (id: string) => void;
  /** Свернуть без нажатия — когда открытого элемента больше нет (удалили). */
  close: () => void;
}

export function useFoldedChoice(param: string): FoldedChoice {
  const screen = useScreenState();
  // Начальное значение — из адреса: после F5 в нём уже стоит раскрытый
  // элемент, и `null` здесь оставил бы панель закрытой при открытом адресе.
  const [chosen, remember] = useState<string | null>(screen.text(param) || null);
  const [shown, setShown] = useState<string | null>(chosen);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const set = (id: string | null) => {
    remember(id);
    screen.set({ [param]: id });
  };

  /**
   * Три случая, и они разные:
   *
   * - тот же самый — свернуть (нажатие повторяет вопрос, ответ — закрыть);
   * - никого не открыто — открыть сразу;
   * - открыт другой — сначала свернуть его, потом открыть нового, иначе
   *   содержимое подменяется под открытой панелью и выглядит как подмена.
   */
  function choose(id: string) {
    if (timer.current) clearTimeout(timer.current);
    if (chosen === id) {
      set(null);
      return;
    }
    if (chosen === null) {
      setShown(id);
      set(id);
      return;
    }
    set(null);
    timer.current = setTimeout(() => {
      setShown(id);
      set(id);
    }, FOLD_MS);
  }

  return { chosen, shown, choose, close: () => set(null) };
}

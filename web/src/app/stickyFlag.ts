/**
 * Признак экрана, который переживает и обновление страницы, и уход с экрана.
 *
 * Адрес отвечает на первое, но не на второе: переход в соседний раздел и
 * возврат по меню приводят на чистый адрес, и открытое окно закрылось бы само.
 * Поэтому признак живёт в двух местах, и у каждого своя работа: **адрес —
 * источник правды** (F5, «назад», ссылка, которую можно послать), **память
 * браузера — только восстановление** при возврате на экран.
 *
 * Расхождение решается в одну сторону: при монтировании адрес, в котором
 * признака нет, дополняется из памяти; всё остальное время пишет адрес. Так
 * человек, снявший признак и ушедший, возвращается без него — снятие тоже
 * запоминается.
 *
 * Ключ памяти включает имя признака: два окна на разных экранах не должны
 * открывать друг друга.
 */
import { useEffect, useState } from 'react';

import { useScreenState } from './screenState';

const PREFIX = 'ahrefs-cases.экран.';

function remembered(name: string): boolean {
  try {
    return localStorage.getItem(PREFIX + name) === 'да';
  } catch {
    // Приватное окно или запрещённые данные сайта: признак просто не
    // переживёт уход с экрана. Ронять из-за этого экран нельзя.
    return false;
  }
}

function remember(name: string, on: boolean): void {
  try {
    if (on) localStorage.setItem(PREFIX + name, 'да');
    else localStorage.removeItem(PREFIX + name);
  } catch {
    // см. `remembered`
  }
}

export function useStickyFlag(name: string): [boolean, (on: boolean) => void] {
  const screen = useScreenState();
  const inAddress = screen.flag(name);
  // Первый кадр: адреса ещё нет, а память уже есть. Читаем её сразу, иначе
  // окно мигнёт закрытым, прежде чем восстановиться.
  const [on, setOn] = useState(inAddress || remembered(name));

  useEffect(() => {
    if (!inAddress && on) screen.set({ [name]: 'да' });
    // Адрес — источник правды, и после первого кадра он ведёт: пришли по
    // ссылке без признака — значит признака нет.
    if (inAddress !== on) setOn(inAddress || (!inAddress && on));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inAddress]);

  return [
    on,
    (next: boolean) => {
      setOn(next);
      remember(name, next);
      screen.set({ [name]: next ? 'да' : null });
    },
  ];
}

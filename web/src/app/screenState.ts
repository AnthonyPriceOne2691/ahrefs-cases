/**
 * Состояние экрана живёт в адресе страницы.
 *
 * Причина простая: F5 не должен стирать работу. Человек отфильтровал проекты,
 * долистал до третьей страницы, обновил вкладку — и оказался в начале. То же
 * при переходе в соседний раздел и обратно.
 *
 * Адрес выбран вместо памяти вкладки, потому что делает ещё две вещи даром:
 * «назад» возвращает к тому, что человек видел, а ссылку на отфильтрованный
 * список можно переслать коллеге. Память вкладки не умеет ни того, ни другого.
 *
 * **Источник правды — состояние экрана, адрес получает копию.** Наоборот было
 * бы стройнее, но экран перерисовывается раньше, чем маршрутизатор довозит
 * новый адрес: панель, открытие которой зависело от адреса, оставалась
 * закрытой, а тумблер версий не доезжал до запроса. Адрес читается один раз —
 * при первом рендере, — и с тех пор только пишется.
 *
 * Правка идёт **пачкой**, а не по одному параметру: смена фильтра сбрасывает
 * страницу, и два отдельных вызова второй перетёр бы первый — он читает
 * параметры такими, какими они были до правки.
 */
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

export type ScreenPatch = Record<string, string | null>;

export interface ScreenState {
  /** Значение параметра или подстановка, если его в адресе нет. */
  text: (name: string, fallback?: string) => string;
  /** Число из адреса. Мусор вместо числа читается как подстановка: адрес
   *  правят руками, и `?page=абв` не должен ронять экран. */
  number: (name: string, fallback: number) => number;
  flag: (name: string) => boolean;
  /** `null` в значении убирает параметр: адрес не хранит умолчания, иначе
   *  ссылка на первую страницу без фильтров выглядит как отчёт. */
  set: (patch: ScreenPatch) => void;
}

export function useScreenState(): ScreenState {
  const [params, setParams] = useSearchParams();

  return {
    text: (name, fallback = '') => params.get(name) ?? fallback,
    number: (name, fallback) => {
      const raw = Number(params.get(name));
      return Number.isFinite(raw) && raw >= 0 ? raw : fallback;
    },
    flag: (name) => params.get(name) === 'да',
    set: (patch) => {
      const next = new URLSearchParams(params);
      for (const [name, value] of Object.entries(patch)) {
        if (value === null || value === '') next.delete(name);
        else next.set(name, value);
      }
      // `replace`, а не push: иначе «назад» разбирает историю фильтров по
      // шагу, вместо того чтобы вернуть человека на прошлый экран.
      setParams(next, { replace: true });
    },
  };
}

/**
 * Страница списка — там же, где остальное состояние экрана.
 *
 * Отдельным хуком, потому что списков два (проекты и кейсы) и будет третий:
 * восемь строк «прочитать номер, положить в состояние, отразить в адресе»
 * скопированные — это ровно то, на чём расходятся экраны, а гейт копипаста
 * ловит их раньше, чем расхождение замечает человек.
 *
 * Номер первой страницы в адрес не пишется: ссылка на список без фильтров
 * должна выглядеть как ссылка на список, а не как отчёт о состоянии.
 */
export function usePagedScreen(): {
  screen: ScreenState;
  page: number;
  setPage: (value: number) => void;
} {
  const screen = useScreenState();
  const [page, remember] = useState(screen.number('page', 0));
  return {
    screen,
    page,
    setPage: (value: number) => {
      remember(value);
      screen.set({ page: value ? String(value) : null });
    },
  };
}

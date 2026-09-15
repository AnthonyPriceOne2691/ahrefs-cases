/**
 * Отметки на кейсах: что выбрано и что с этим можно сделать.
 *
 * Выбор живёт в памяти экрана, а не в адресе: список страничный, а отмеченное
 * относится к тому, что человек видит сейчас. Адрес пережил бы смену фильтра
 * версий и увёз бы в закладку номера кейсов, которых в новом списке нет.
 *
 * Отдельным файлом — потому что это состояние со своими правилами (отмечать
 * можно только строки с файлом), а не три строки внутри экрана.
 */
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { downloadCase, downloadSelection } from '../../api/cases';
import type { CaseRow } from '../../api/types';

import { saveFile } from './save';

export interface Selection {
  chosen: number[];
  has: (id: number) => boolean;
  pick: (id: number, checked: boolean) => void;
  pickAll: (checked: boolean) => void;
  clear: () => void;
}

/** Отмечать нечего у строк без файла: кейс в базе есть, а скачивать нечего. */
export function takeable(rows: readonly CaseRow[]): CaseRow[] {
  return rows.filter((row) => row.filename !== null);
}

export function useCaseSelection(rows: readonly CaseRow[]): Selection {
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());

  return {
    chosen: [...selected],
    has: (id: number) => selected.has(id),
    pick: (id: number, checked: boolean) =>
      setSelected((was) => {
        const next = new Set(was);
        if (checked) next.add(id);
        else next.delete(id);
        return next;
      }),
    pickAll: (checked: boolean) =>
      setSelected(checked ? new Set(takeable(rows).map((row) => row.id)) : new Set<number>()),
    clear: () => setSelected(new Set<number>()),
  };
}

/**
 * Скачать отмеченное.
 *
 * Один выбранный уезжает PDF-файлом, несколько — одним архивом. Архив для
 * одного файла был бы издевательством: человек просил кейс, а распаковывать
 * ради него ZIP не подряжался. Пачкой отдельных загрузок несколько отдать
 * нельзя вовсе — браузер разрешает вкладке одну загрузку за жест и остальные
 * обрывает молча.
 */
export function useSelectionDownload(
  chosen: number[],
  rows: readonly CaseRow[],
  onFailure: (error: unknown) => void,
) {
  return useMutation({
    mutationFn: () => {
      const [single] = chosen;
      if (chosen.length === 1 && single !== undefined) {
        const only = rows.find((row) => row.id === single);
        return downloadCase(single, only?.filename ?? `кейс-${single}.pdf`);
      }
      return downloadSelection(chosen, 'выборка-кейсов.zip');
    },
    onSuccess: saveFile,
    onError: onFailure,
  });
}

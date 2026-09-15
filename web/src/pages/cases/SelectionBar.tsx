/**
 * Панель выбранных кейсов: скачать отмеченное или снять отметки.
 *
 * Кнопки появляются только когда есть что скачивать: две серые кнопки над
 * пустым выбором — шум, который учатся не замечать, и тогда его не видят и
 * тогда, когда он нужен.
 *
 * **Место под панель занято всегда.** Пустой `null` убирал её из потока, и
 * первая же отметка сдвигала вниз всю таблицу: строка, по которой человек
 * только что щёлкнул, уезжала из-под курсора, а следующую он отмечал вслепую.
 * Высота задана числом, а не отступом на глаз: столько занимает кнопка размера
 * по умолчанию (найдено владельцем 15.09.2026).
 */
import { Box, Button, Group } from '@mantine/core';

/** Высота кнопки Mantine размера `sm` — ровно столько и резервируем. */
const BAR_HEIGHT = 36;

interface Props {
  count: number;
  busy: boolean;
  onTake: () => void;
  onClear: () => void;
}

export function SelectionBar({ count, busy, onTake, onClear }: Props) {
  if (count === 0) return <Box mih={BAR_HEIGHT} data-selection-bar="empty" aria-hidden />;
  return (
    <Group gap="sm" align="center" mih={BAR_HEIGHT} data-selection-bar="filled">
      <Button loading={busy} onClick={onTake}>
        {/* Один выбранный — это PDF, а не архив из одного файла, и подпись
            обязана обещать именно то, что приедет. «Скачать выбранный PDF», а
            не «Скачать PDF»: вторая подпись уже занята кнопкой в строке. */}
        {count === 1 ? 'Скачать выбранный PDF' : `Скачать выбранные (${count}) одним ZIP`}
      </Button>
      <Button variant="subtle" onClick={onClear}>
        Снять выделение
      </Button>
    </Group>
  );
}

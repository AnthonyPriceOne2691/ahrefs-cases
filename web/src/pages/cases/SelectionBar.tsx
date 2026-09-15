/**
 * Панель выбранных кейсов: скачать отмеченное или снять отметки.
 *
 * Появляется только когда есть что скачивать: две серые кнопки над пустым
 * выбором — шум, который учатся не замечать, и тогда его не видят и тогда,
 * когда он нужен.
 */
import { Button, Group } from '@mantine/core';

interface Props {
  count: number;
  busy: boolean;
  onTake: () => void;
  onClear: () => void;
}

export function SelectionBar({ count, busy, onTake, onClear }: Props) {
  if (count === 0) return null;
  return (
    <Group gap="sm" align="center">
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

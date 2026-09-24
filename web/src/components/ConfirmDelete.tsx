/**
 * «Да, удалить» и «Отмена» — пара кнопок подтверждения необратимого шага.
 *
 * Одна на все удаления с подтверждением на месте (человек, проект): вторая
 * копия появилась с удалением проекта, и гейт копипаста справедливо её поймал —
 * разошлись бы они на первой же правке, скажем, в том, что «удалить» недоступна,
 * пока не известно, что уйдёт.
 */
import { Button, Group } from '@mantine/core';

interface Props {
  busy: boolean;
  /** Подтверждать ещё нечего: например, не пришёл предпросмотр последствий. */
  disabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDelete({ busy, disabled = false, onConfirm, onCancel }: Props) {
  return (
    <Group mt="sm">
      <Button size="compact-sm" color="red" disabled={disabled} loading={busy} onClick={onConfirm}>
        Да, удалить
      </Button>
      <Button size="compact-sm" variant="subtle" onClick={onCancel}>
        Отмена
      </Button>
    </Group>
  );
}

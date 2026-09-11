/**
 * Листание страниц.
 *
 * Страницы, а не бесконечная лента: у сервера жёсткий потолок выдачи, и лента
 * скрыла бы от человека, что он видит не всё.
 */
import { Button, Group, Text } from '@mantine/core';

interface Props {
  page: number;
  full: boolean;
  onChange: (page: number) => void;
}

export function Pager({ page, full, onChange }: Props) {
  return (
    <Group justify="flex-end">
      <Button variant="light" disabled={page === 0} onClick={() => onChange(Math.max(0, page - 1))}>
        Назад
      </Button>
      <Text size="sm">Страница {page + 1}</Text>
      {/* Полная страница означает «возможно, есть ещё», а не «точно есть». */}
      <Button variant="light" disabled={!full} onClick={() => onChange(page + 1)}>
        Вперёд
      </Button>
    </Group>
  );
}

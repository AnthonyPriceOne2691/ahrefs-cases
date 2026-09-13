/**
 * Кого прогон не собрал и почему.
 *
 * «17 из 19» — это вопрос, а не ответ: пропуск бывает четырёх видов, и человек
 * по ним делает разное (докупить историю, поправить строку списка, поднять
 * лимит units, перезапустить). ТЗ требует этого прямо: «сколько обработано,
 * сколько пропущено и почему».
 *
 * Спрашивается по требованию, а не вместе с журналом: журнал опрашивается по
 * таймеру, пока идёт прогон, и таскать список судеб каждые пять секунд ради
 * строки, которую никто не открыл, незачем.
 */
import { Alert, Button, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError } from '../../api/client';
import { fetchRun } from '../../api/ops';
import { fateWord } from '../status';

/** Тело раскрытия отдельным компонентом: у списка четыре состояния (грузится,
 *  отказ, пусто, строки), и вместе с кнопкой они дают ветвистость, на которую
 *  справедливо ругается гейт сложности. */
function Fates({ runId }: { runId: number }) {
  const card = useQuery({ queryKey: ['runs', runId, 'fates'], queryFn: () => fetchRun(runId) });

  if (card.isPending) return <Text size="xs">Читаем журнал…</Text>;
  if (card.isError) {
    return (
      <Alert color="red" variant="light">
        <Text size="xs">
          {card.error instanceof ApiError ? card.error.message : 'судьбы не загрузились'}
        </Text>
      </Alert>
    );
  }
  if (card.data.fates.length === 0) {
    return (
      <Text size="xs" c="dimmed">
        записей по доменам нет: прогон не дошёл до сбора
      </Text>
    );
  }

  return (
    <Table>
      <Table.Tbody>
        {card.data.fates.map((fate) => (
          <Table.Tr key={fate.domain} data-fate={fate.domain}>
            <Table.Td>
              <Text size="xs">{fate.domain}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="xs">{fateWord(fate.outcome)}</Text>
            </Table.Td>
            <Table.Td>
              <Text size="xs" c="dimmed">
                {fate.reason || '—'}
              </Text>
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

export function RunFates({ runId, skipped }: { runId: number; skipped: number }) {
  const [opened, setOpened] = useState(false);

  if (skipped <= 0) return null;

  return (
    <Stack gap={4}>
      <Text size="xs" c="orange" data-run-skipped={skipped}>
        пропущено {skipped}
      </Text>
      {/* Инлайн-раскрытие, а не модальное окно: попапы Mantine в jsdom
          рендерятся секундами, и оракул на них уходит в таймаут (урок из Ф6). */}
      <Button
        size="compact-xs"
        variant="subtle"
        onClick={() => setOpened((was) => !was)}
        data-run-why={runId}
      >
        {opened ? 'скрыть' : 'почему'}
      </Button>
      {opened && <Fates runId={runId} />}
    </Stack>
  );
}

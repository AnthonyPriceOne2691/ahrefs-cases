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
import { ActionIcon, Alert, Collapse, Group, Stack, Table, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { FOLD_MS } from '../../app/foldedChoice';
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

/** Знак вопроса рядом с числом пропущенных.
 *
 * Прежде здесь стояло слово «почему» кнопкой, и оно занимало в колонке больше
 * места, чем само число: колонка «Проекты» раздувалась ради подписи, которую
 * читают один раз (замечание владельца 15.09.2026). Жёлтый — того же цвета,
 * что «пропущено N»: знак принадлежит этой строке, а не таблице вообще.
 *
 * `aria-label` обязателен: знак вопроса сам по себе не говорит, о чём спросят.
 */
export function WhySkipped({
  runId,
  skipped,
  failed,
  opened,
  onToggle,
}: {
  runId: number;
  skipped: number;
  /** Прогон упал с причиной. Знак нужен и тогда, когда пропущенных нет вовсе:
   *  причина отказа — единственное объяснение упавшего прогона. */
  failed: boolean;
  opened: boolean;
  onToggle: () => void;
}) {
  if (skipped <= 0 && !failed) return null;
  return (
    <Group gap={6} justify="center">
      {skipped > 0 && (
        <Text size="xs" c="orange" data-run-skipped={skipped}>
          пропущено {skipped}
        </Text>
      )}
      <ActionIcon
        size="xs"
        radius="xl"
        variant={opened ? 'filled' : 'light'}
        color="yellow"
        onClick={onToggle}
        aria-label={opened ? 'скрыть, почему пропущены' : 'почему пропущены'}
        data-run-why={runId}
      >
        ?
      </ActionIcon>
    </Group>
  );
}

/** Раскрытие живёт ОТДЕЛЬНОЙ строкой таблицы во всю ширину.
 *
 * Внутри ячейки список судеб раздвигал свою колонку, и остальные прыгали —
 * именно это владелец и просил убрать. Строка на всю ширину меняет высоту
 * таблицы и не трогает ни одной колонки.
 */
export function FatesRow({
  runId,
  error,
  columns,
  background,
  opened,
  shown,
}: {
  runId: number;
  /** Причина отказа как её записал прогон. Живёт здесь, а не в ячейке
   *  таблицы: владелец увидел `MissingGreenlet: greenlet_spawn has not been
   *  called…` строкой на всю ширину экрана (15.09.2026). Прятать её нельзя —
   *  это единственное объяснение упавшего прогона, — но место ей в раскрытии. */
  error: string;
  columns: number;
  /** Фон полосы своего прогона: раскрытие — продолжение его строки. */
  background: string | undefined;
  opened: boolean;
  /** Чьи судьбы показывать: отстаёт от `opened` на время сворачивания, иначе
   *  сворачивать будет нечего. */
  shown: boolean;
}) {
  if (!shown) return null;
  return (
    <Table.Tr data-fates-row={runId} bg={background}>
      {/* `p: 0` у закрытого раскрытия: иначе пустая строка держит отступы и
          таблица всё равно подрастает на пару пикселей. */}
      <Table.Td colSpan={columns} style={{ padding: opened ? undefined : 0 }}>
        <Collapse in={opened} transitionDuration={FOLD_MS}>
          <Stack gap="xs">
            {error && (
              <Alert color="red" variant="light" data-run-error>
                <Text size="xs">Прогон отказал: {error}</Text>
              </Alert>
            )}
            <Fates runId={runId} />
          </Stack>
        </Collapse>
      </Table.Td>
    </Table.Tr>
  );
}

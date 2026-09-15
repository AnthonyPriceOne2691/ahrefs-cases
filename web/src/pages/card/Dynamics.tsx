/**
 * Блок «Динамика»: кривые и шаг, которым они нарисованы.
 *
 * Отдельным файлом не ради красоты: карточка проекта собирает шесть блоков, и
 * каждый, оставленный в ней целиком, отодвигает следующий за предел, после
 * которого страницу перестают читать сверху вниз.
 */
import { Paper, Stack, Text, Title } from '@mantine/core';

import type { Grouping } from '../../api/projects';
import type { ChartBlock } from '../../api/types';

import { Charts } from './Charts';

interface Props {
  blocks: ChartBlock[] | undefined;
  pending: boolean;
  /**
   * Кривые на экране от прежнего шага, новые ещё грузятся. Блок приглушается,
   * а не снимается: подмена рисунка без всякого знака читалась бы как «ничего
   * не произошло», а снятие роняло бы высоту страницы и уводило прокрутку.
   */
  stale: boolean;
  grouping: Grouping;
  onGrouping: (value: Grouping) => void;
}

export function Dynamics({ blocks, pending, stale, grouping, onGrouping }: Props) {
  return (
    <Paper className="glass" p="lg">
      <Stack gap="sm">
        <Title order={3}>Динамика</Title>
        {pending && <Text size="sm">Рисуем кривые…</Text>}
        {blocks && (
          <Charts blocks={blocks} grouping={grouping} onGrouping={onGrouping} stale={stale} />
        )}
      </Stack>
    </Paper>
  );
}

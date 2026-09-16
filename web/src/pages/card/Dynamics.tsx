/**
 * Блок «Динамика»: кривые и шаг, которым они нарисованы.
 *
 * Отдельным файлом не ради красоты: карточка проекта собирает шесть блоков, и
 * каждый, оставленный в ней целиком, отодвигает следующий за предел, после
 * которого страницу перестают читать сверху вниз.
 */
import { Paper, Skeleton, Stack, Title } from '@mantine/core';

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
        {/*
          Место под кривые занято ЗАРАНЕЕ, пока они грузятся. Прежде здесь
          стояла строка «Рисуем кривые…», и блок держал высоту одной строки:
          приходили графики — страница подпрыгивала на несколько сотен
          пикселей, и это читалось как мигание (замечание владельца
          16.09.2026). Заглушка той же высоты, что рисунок, убирает скачок:
          два графика по 220 пикселей — столько же занимает пара кривых.
        */}
        {pending ? (
          <Stack gap="lg" data-drawing="true">
            <Skeleton height={20} width={180} radius="sm" />
            <Skeleton height={220} radius="md" />
            <Skeleton height={220} radius="md" />
          </Stack>
        ) : (
          blocks && (
            <Charts blocks={blocks} grouping={grouping} onGrouping={onGrouping} stale={stale} />
          )
        )}
      </Stack>
    </Paper>
  );
}

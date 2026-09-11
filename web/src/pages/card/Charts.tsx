/**
 * Кривые проекта — **тот же рисунок**, что уходит в PDF.
 *
 * SVG вставляется разметкой, а не рисуется здесь: его собрал наш бэкенд из
 * наших же чисел (`export.charts`), и это осознанная граница доверия — чужая
 * разметка сюда не попадает ни на каком пути. Рисовать по рядам на фронте
 * значило бы завести второй рисунок, который разойдётся с печатным.
 */
import { Group, SegmentedControl, Stack, Text, Title } from '@mantine/core';

import type { Grouping } from '../../api/projects';
import type { ChartBlock } from '../../api/types';

const STEPS = [
  { value: 'month', label: 'месяц' },
  { value: 'quarter', label: 'квартал' },
  { value: 'year', label: 'год' },
];

interface Props {
  blocks: ChartBlock[];
  grouping: Grouping;
  onGrouping: (value: Grouping) => void;
}

export function Charts({ blocks, grouping, onGrouping }: Props) {
  const step = (
    <Group justify="flex-end">
      <SegmentedControl
        size="xs"
        value={grouping}
        onChange={(value) => onGrouping(value as Grouping)}
        data={STEPS}
        aria-label="Шаг кривой"
      />
    </Group>
  );

  if (blocks.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Кривых нет: помесячных рядов по этому проекту не собрано. Пустые оси сказали бы «роста не
        было», хотя метрику просто не покупали.
      </Text>
    );
  }
  return (
    <Stack gap="lg">
      {step}
      {blocks.map((block) => (
        <Stack key={block.title} gap="xs">
          <Title order={4}>{block.title}</Title>
          <div
            data-chart={block.title}
            // SVG собран нашим бэкендом из наших чисел — см. докстринг файла.
            dangerouslySetInnerHTML={{ __html: block.svg }}
          />
        </Stack>
      ))}
    </Stack>
  );
}

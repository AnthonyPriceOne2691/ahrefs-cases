/**
 * Кривые проекта — **тот же рисунок**, что уходит в PDF.
 *
 * SVG вставляется разметкой, а не рисуется здесь: его собрал наш бэкенд из
 * наших же чисел (`export.charts`), и это осознанная граница доверия — чужая
 * разметка сюда не попадает ни на каком пути. Рисовать по рядам на фронте
 * значило бы завести второй рисунок, который разойдётся с печатным.
 */
import { Stack, Text, Title } from '@mantine/core';

import type { ChartBlock } from '../../api/types';

export function Charts({ blocks }: { blocks: ChartBlock[] }) {
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

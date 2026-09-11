/**
 * Главный результат крупно — как в кейсе: рост органического трафика.
 *
 * Трафик выбран не вкусом: он главная метрика классификации по ТЗ, и человек,
 * открывший карточку, первым делом ищет именно его.
 */
import { Stack, Text } from '@mantine/core';

import type { ComparisonRow } from '../../api/types';
import { growth, num } from '../format';

const HERO_SUBJECT = 'org_traffic';

export function Hero({ rows }: { rows: ComparisonRow[] }) {
  const hero = rows.find((row) => row.subject === HERO_SUBJECT);
  if (!hero) return null;
  return (
    <Stack gap={0} data-hero={HERO_SUBJECT}>
      <Text fz={40} fw={700} lh={1.1}>
        {growth(hero.pct, hero.absolute)}
      </Text>
      <Text size="sm" c="dimmed">
        {hero.label}: {num(hero.before)} → {num(hero.after)}
      </Text>
    </Stack>
  );
}

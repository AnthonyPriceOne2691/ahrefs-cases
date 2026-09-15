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
  /** Кривые на экране от прежнего шага, новые ещё грузятся. */
  stale?: boolean;
}

export function Charts({ blocks, grouping, onGrouping, stale = false }: Props) {
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
      <Stack gap="lg">
        {/*
          Переключатель остаётся ВСЕГДА, даже когда рисовать нечего. Прежде он
          стоял после этого возврата и исчезал вместе с кривыми: человек
          переключался на квартал, получал пустоту — и вернуться на месяц было
          уже нечем. Тупик, из которого выходили перезагрузкой страницы
          (найдено владельцем 15.09.2026 на `tally.so`).
        */}
        {step}
        <Text size="sm" c="dimmed">
          {grouping === 'month'
            ? // Помесячных рядов действительно нет: метрику не покупали. Пустые
              // оси сказали бы «роста не было» (урок L30).
              'Кривых нет: помесячных рядов по этому проекту не собрано. Пустые оси сказали бы «роста не было», хотя метрику просто не покупали.'
            : // А здесь ряды есть — их просто не хватает на этом шаге: у
              // короткого периода квартал или год схлопываются в одну точку, а
              // кривой по одной точке не бывает.
              'На этом шаге точек слишком мало: период работ короче одного шага, и кривая свернулась в точку. Возьмите шаг мельче.'}
        </Text>
      </Stack>
    );
  }
  return (
    <Stack gap="lg">
      {/* Переключатель ВНЕ приглушаемой области: он не рисунок, а орган
          управления, и гаснуть под пальцем ему незачем. */}
      {step}
      <Stack
        gap="lg"
        data-stale={stale || undefined}
        // Переход задан здесь, а не в glass.css: правило касается одного этого
        // блока, и держать его рядом с разметкой честнее, чем в общем файле
        // оформления, где оно переживёт свой повод.
        style={{ transition: 'opacity 180ms ease', opacity: stale ? 0.45 : 1 }}
      >
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
    </Stack>
  );
}

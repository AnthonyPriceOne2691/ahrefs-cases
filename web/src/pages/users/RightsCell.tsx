/**
 * Права человека в строке: что можно и **почему**.
 *
 * Цвет здесь несёт смысл, а не украшает: серое — как у всех в группе, синее —
 * выдано лично поверх группы, красное — отобрано лично, хотя группа даёт.
 * Последнее и есть случай, ради которого экран нужен: по названию группы его
 * не увидеть никак.
 */
import { Badge, Group, Text } from '@mantine/core';

import type { RightState } from './rights';
import { rightLabel } from './rights';

const COLOR: Record<RightState['origin'], string> = {
  группа: 'gray',
  'выдано лично': 'blue',
  'отобрано лично': 'red',
};

export function RightsCell({ states }: { states: RightState[] }) {
  if (states.length === 0) {
    return (
      <Text size="xs" c="dimmed">
        прав нет
      </Text>
    );
  }
  return (
    <Group gap={4}>
      {states.map((state) => (
        <Badge
          key={state.right}
          size="sm"
          variant="light"
          color={COLOR[state.origin]}
          data-origin={state.origin}
          // Зачёркнутое право читается как «было и отняли» — это и произошло.
          style={state.allowed ? undefined : { textDecoration: 'line-through' }}
          title={`${rightLabel(state.right)}: ${state.origin}`}
        >
          {rightLabel(state.right)}
        </Badge>
      ))}
    </Group>
  );
}

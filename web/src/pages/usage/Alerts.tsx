/**
 * Поводы, о которых оператор должен узнать сам.
 *
 * Степеней четыре, а не две: «готовая пачка» и «мало units» одним цветом
 * читаются как одно и то же, а действия по ним противоположные — забрать архив
 * против «остановись и подними лимит».
 *
 * Пустой список — это ответ «проверили, чисто», а не тишина. Разница ровно
 * такая же, как между «данных нет» и «ноль» в остальном сервисе.
 */
import { Alert, Stack, Text } from '@mantine/core';

import type { AlertView } from '../../api/types';

const COLORS: Record<string, string> = {
  critical: 'red',
  serious: 'orange',
  warning: 'yellow',
  good: 'teal',
};

export function Alerts({ rows }: { rows: AlertView[] }) {
  if (rows.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Поводов нет: остатка хватает, упавших прогонов нет, новой пачки кейсов тоже.
      </Text>
    );
  }
  return (
    <Stack gap="xs">
      {rows.map((row) => (
        <Alert
          key={`${row.kind}-${row.message}`}
          color={COLORS[row.severity] ?? 'gray'}
          variant="light"
          data-severity={row.severity}
          data-kind={row.kind}
        >
          <Text size="sm">{row.message}</Text>
        </Alert>
      ))}
    </Stack>
  );
}

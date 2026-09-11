/**
 * Состояние прогона, запущенного с этого экрана.
 *
 * Нажавший кнопку человек не должен перезагружать страницу, чтобы узнать,
 * началось ли: журнал прогонов приедет отдельным экраном, а эта строка отвечает
 * на вопрос «моё нажатие сработало?».
 */
import { Alert, Text } from '@mantine/core';

import type { RunRow } from '../../api/types';

export const RUNNING = new Set(['queued', 'running']);

export function RunLine({ run }: { run: RunRow }) {
  return (
    <Alert color={RUNNING.has(run.status) ? 'blue' : 'teal'} variant="light">
      <Text size="sm">
        Прогон №{run.id}: {run.status}, проектов {run.projects_ok} из {run.projects_total},
        потрачено units {run.units_actual}.{run.error && ` Причина: ${run.error}`}
      </Text>
    </Alert>
  );
}

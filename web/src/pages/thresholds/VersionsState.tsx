/**
 * Состояния списка версий, в которых показывать нечего.
 *
 * Жили в карточке «Действующая версия», а её сняли (15.09.2026): подробности
 * версии дословно повторялись в раскрытии списка ниже. Но вместе с карточкой
 * ушли бы и эти три ответа — а они как раз про случаи, когда списка нет вовсе,
 * и раскрывать нечего.
 */
import { Alert, Paper, Stack, Text } from '@mantine/core';

import { failureText } from '../cases/failure';

interface Props {
  pending: boolean;
  error: unknown;
  empty: boolean;
}

export function VersionsState({ pending, error, empty }: Props) {
  if (!pending && !empty && (error === null || error === undefined)) return null;
  return (
    <Paper className="glass" p="lg">
      <Stack gap="md">
        {pending && <Text size="sm">Загружаем версии…</Text>}

        {error !== null && error !== undefined && (
          <Alert color="red" variant="light">
            <Text size="sm">{failureText(error, 'версии не загрузились')}</Text>
          </Alert>
        )}

        {empty && (
          <Alert color="yellow" variant="light">
            <Text size="sm">
              Версий порогов нет. Первая заводится при старте сервиса из файла-сида — если её нет,
              классифицировать нечем.
            </Text>
          </Alert>
        )}
      </Stack>
    </Paper>
  );
}

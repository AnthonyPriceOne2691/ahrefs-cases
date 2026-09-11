/**
 * Карточка действующих порогов: что сейчас решает группы.
 *
 * Отдельно от списка версий, потому что отвечает на другой вопрос: не «какие
 * версии есть», а «по чему считается то, что я вижу на остальных экранах».
 */
import { Alert, Paper, Stack, Text, Title } from '@mantine/core';

import type { RulesetRow } from '../../api/types';
import { failureText } from '../cases/failure';

import { RulesView } from './RulesView';
import { readRules } from './rules';

interface Props {
  current: RulesetRow | null;
  pending: boolean;
  error: unknown;
  empty: boolean;
}

export function CurrentVersion({ current, pending, error, empty }: Props) {
  return (
    <Paper className="glass" p="lg">
      <Stack gap="md">
        <Title order={4}>
          {current?.is_active ? 'Действующая версия' : 'Версия'} {current?.version ?? ''}
        </Title>

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

        {current && <RulesView rules={readRules(current.payload)} />}
      </Stack>
    </Paper>
  );
}

/**
 * Смета прогона и кнопка запуска.
 *
 * Главное свойство экрана: **отказ виден до траты, а не после**. Прогон стоит
 * units, бюджет заказчика на первичный прогон — 10 000, и кнопка, позволяющая
 * начать прогон, обречённый упереться в квоту, дороже любой вёрстки.
 *
 * Кнопка при этом не прячется, а становится недоступной с подписью: пропавшая
 * кнопка не объясняет, почему её нет, и человек идёт искать поломку вместо
 * того, чтобы поднять лимит.
 *
 * Причин две и они разные (урок L23): «не хватает units» лечится ожиданием или
 * лимитом, «остаток неизвестен» — починкой доступа к Ahrefs. Одна серая плашка
 * на оба случая отправила бы человека не туда.
 */
import { Alert, Badge, Button, Code, Group, Stack, Text, Title } from '@mantine/core';

import type { RunEstimate, RunRow } from '../../api/types';

import { RunLine } from './RunLine';

interface Props {
  estimate: RunEstimate;
  run: RunRow | null;
  starting: boolean;
  startError: string | null;
  onStart: () => void;
}

function quotaText(estimate: RunEstimate): string {
  const left =
    estimate.quota_left === null ? 'неизвестен' : estimate.quota_left.toLocaleString('ru-RU');
  const held =
    estimate.quota_reserved > 0
      ? `, из них удержано идущими прогонами ${estimate.quota_reserved}`
      : '';
  return `Остаток квоты: ${left}${held}`;
}

function Numbers({ estimate }: { estimate: RunEstimate }) {
  return (
    <Group gap="xs">
      <Badge size="lg" variant="light">
        проектов {estimate.projects}
      </Badge>
      <Badge size="lg" variant="light" color="grape">
        units по смете {estimate.units_estimated}
      </Badge>
      <Badge size="lg" variant="light">
        запросов {estimate.requests_planned}
      </Badge>
      {estimate.requests_cached > 0 && (
        <Badge size="lg" variant="light" color="teal">
          уже собрано {estimate.requests_cached}
        </Badge>
      )}
    </Group>
  );
}

function Refusal({ estimate }: { estimate: RunEstimate }) {
  if (estimate.may_start) return null;
  return (
    <Alert color={estimate.verdict === 'unknown' ? 'yellow' : 'red'} variant="light">
      <Text size="sm">{estimate.reason || 'прогон сейчас начать нельзя'}</Text>
    </Alert>
  );
}

export function EstimatePanel({ estimate, run, starting, startError, onStart }: Props) {
  const empty = estimate.projects === 0;

  return (
    <Stack gap="sm">
      <Title order={4}>Смета прогона</Title>
      <Numbers estimate={estimate} />
      <Text size="sm">{quotaText(estimate)}</Text>
      {estimate.scheme_lines.length > 0 && <Code block>{estimate.scheme_lines.join('\n')}</Code>}
      <Refusal estimate={estimate} />

      {startError && (
        <Alert color="red" variant="light">
          <Text size="sm">{startError}</Text>
        </Alert>
      )}

      <Group>
        <Button
          onClick={onStart}
          loading={starting}
          disabled={!estimate.may_start || empty}
          data-testid="start-run"
        >
          Запустить прогон
        </Button>
        {empty && <Text size="sm">Сначала загрузите список.</Text>}
      </Group>

      {run && <RunLine run={run} />}
    </Stack>
  );
}

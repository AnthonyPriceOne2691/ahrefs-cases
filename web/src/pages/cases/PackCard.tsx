/**
 * Пачка кейсов — выход сервиса по ТЗ.
 *
 * Пачка одна: сборка кладёт архив в каталог выгрузки и переписывает вчерашний.
 * Поэтому здесь не список, а состояние: что лежит, когда собрано и можно ли
 * это забрать. Кнопка сборки стоит рядом с ответом «пачки нет» нарочно —
 * иначе человек читает отказ и не знает, чем его исправить.
 */
import { Alert, Button, Group, Stack, Text, Title } from '@mantine/core';
import { Link } from 'react-router-dom';

import type { PackView } from '../../api/types';
import { num } from '../format';

/** Размер в мегабайтах: байты в пачке PDF — это число, которое никто не читает. */
function size(bytes: number | null): string {
  if (bytes === null) return '—';
  return `${num(Math.max(1, Math.round(bytes / 1024 / 1024)))} МБ`;
}

function moment(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

interface Props {
  pack: PackView;
  /** Право `run`: сборка кейсов — это прогон, и открыт он не всем. */
  canRun: boolean;
  downloading: boolean;
  rebuilding: boolean;
  startedRunId: number | null;
  error: string | null;
  onDownload: () => void;
  onRebuild: () => void;
}

export function PackCard({
  pack,
  canRun,
  downloading,
  rebuilding,
  startedRunId,
  error,
  onDownload,
  onRebuild,
}: Props) {
  return (
    <Stack gap="sm">
      <Title order={4}>Пачка целиком</Title>

      {pack.exists ? (
        <Text size="sm">
          {pack.filename} · {size(pack.size_bytes)} · собрана {moment(pack.built_at)}
        </Text>
      ) : (
        <Alert color="yellow" variant="light">
          <Text size="sm">{pack.note}</Text>
        </Alert>
      )}

      <Group gap="sm">
        <Button disabled={!pack.exists} loading={downloading} onClick={onDownload}>
          Скачать ZIP
        </Button>
        {/* Кнопки нет вовсе, а не «нажми и получи 403»: право проверяет сервер,
            а интерфейс не должен обещать того, чего не даст. */}
        {canRun && (
          <Button variant="light" loading={rebuilding} onClick={onRebuild}>
            Пересобрать кейсы
          </Button>
        )}
      </Group>

      {startedRunId !== null && (
        <Alert color="teal" variant="light">
          <Text size="sm">
            Сборка идёт прогоном №{startedRunId}. Он длится минуты: следить за ним —{' '}
            <Link to="/runs">в журнале прогонов</Link>, а пачка обновится здесь, когда прогон
            закончится.
          </Text>
        </Alert>
      )}

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}

      <Text size="xs" c="dimmed">
        Внутри архива лежит список «кейсы.csv» с группой и пометкой «можно публиковать» — по нему и
        смотрят пачку перед отправкой клиенту.
      </Text>
    </Stack>
  );
}

/**
 * Тело экрана: одно из пяти состояний.
 *
 * Вынесено из страницы не ради красоты — состояний действительно пять, и
 * ветвление между ними живёт в одном месте, а не размазано по разметке вместе
 * с фильтрами и листанием.
 */
import { Alert, Text } from '@mantine/core';

import { ApiError } from '../../api/client';
import type { ProjectRow } from '../../api/types';

import { EmptyState } from './EmptyState';
import { ProjectsTable } from './ProjectsTable';

interface Props {
  rows: ProjectRow[] | undefined;
  loading: boolean;
  error: unknown;
  filtered: boolean;
  onOpen: (project: ProjectRow) => void;
}

export function ProjectsBody({ rows, loading, error, filtered, onOpen }: Props) {
  if (loading) return <Text size="sm">Загружаем проекты…</Text>;
  if (error) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">
          {error instanceof ApiError ? error.message : 'проекты не загрузились'}
        </Text>
      </Alert>
    );
  }
  if (!rows) return null;
  if (rows.length === 0) return <EmptyState filtered={filtered} />;
  return <ProjectsTable rows={rows} onOpen={onOpen} />;
}

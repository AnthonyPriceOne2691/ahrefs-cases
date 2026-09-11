/**
 * Список версий и предпросмотр выбранной.
 *
 * Предпросмотр стоит рядом со списком нарочно: вопрос «что изменится» задают о
 * конкретной версии, и ответ, уехавший в другой угол экрана, приходится
 * сопоставлять по памяти.
 */
import { Alert, Paper, Stack, Text, Title } from '@mantine/core';

import type { PreviewView, RulesetRow } from '../../api/types';

import { PreviewPanel } from './PreviewPanel';
import { VersionsTable } from './VersionsTable';

interface Props {
  rows: RulesetRow[];
  selected: string | null;
  busyVersion: string | null;
  preview: PreviewView | null;
  error: string | null;
  onSelect: (row: RulesetRow) => void;
  onPreview: (row: RulesetRow) => void;
}

export function VersionsSection({
  rows,
  selected,
  busyVersion,
  preview,
  error,
  onSelect,
  onPreview,
}: Props) {
  return (
    <Paper className="glass" p="lg">
      <Stack gap="md">
        <Title order={4}>Версии</Title>
        <VersionsTable
          rows={rows}
          selected={selected}
          busyVersion={busyVersion}
          onSelect={onSelect}
          onPreview={onPreview}
        />

        {error && (
          <Alert color="red" variant="light">
            <Text size="sm">{error}</Text>
          </Alert>
        )}

        {preview && <PreviewPanel preview={preview} />}
      </Stack>
    </Paper>
  );
}

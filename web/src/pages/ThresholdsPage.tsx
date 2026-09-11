/**
 * Пороги: что утверждено сейчас и что будет, если применить другую версию.
 *
 * Самое опасное место сервиса — одна цифра перекладывает по группам всю базу и
 * решает, какие кейсы уйдут клиентам. Поэтому экран сначала отвечает
 * «что действует», и только потом — «что изменится».
 *
 * Раздел закрыт правом `edit_thresholds` — так говорит таблица доступа ТЗ, и
 * то, что предпросмотр в API открыт праву `read`, её не отменяет (урок L94).
 * Правка приедет следующей поставкой и будет закрыта тем же правом на сервере.
 */
import { Container, Stack, Title } from '@mantine/core';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { fetchRulesets, previewRuleset } from '../api/thresholds';
import type { PreviewView, RulesetRow } from '../api/types';

import { failureText } from './cases/failure';
import { CurrentVersion } from './thresholds/CurrentVersion';
import { VersionsSection } from './thresholds/VersionsSection';

/** Показываем выбранную версию, а по умолчанию — действующую: именно по ней
 *  посчитаны вердикты, которые человек видит на остальных экранах. */
function shown(rows: RulesetRow[] | undefined, chosen: string | null): RulesetRow | null {
  if (!rows || rows.length === 0) return null;
  if (chosen) return rows.find((row) => row.version === chosen) ?? null;
  return rows.find((row) => row.is_active) ?? rows[0] ?? null;
}

export function ThresholdsPage() {
  const [chosen, setChosen] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewView | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [busyVersion, setBusyVersion] = useState<string | null>(null);

  const rulesets = useQuery({ queryKey: ['rulesets'], queryFn: () => fetchRulesets() });
  const rows = rulesets.data ?? [];
  const current = shown(rulesets.data, chosen);

  const ask = useMutation({
    mutationFn: (row: RulesetRow) => previewRuleset(row.version),
    onMutate: (row: RulesetRow) => {
      setPreviewError(null);
      setPreview(null);
      setBusyVersion(row.version);
    },
    onSuccess: setPreview,
    onError: (error: unknown) => setPreviewError(failureText(error, 'предпросмотр не посчитался')),
    onSettled: () => setBusyVersion(null),
  });

  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Пороги</Title>

        <CurrentVersion
          current={current}
          pending={rulesets.isPending}
          error={rulesets.isError ? rulesets.error : null}
          empty={rulesets.isSuccess && rows.length === 0}
        />

        {rows.length > 0 && (
          <VersionsSection
            rows={rows}
            selected={current?.version ?? null}
            busyVersion={busyVersion}
            preview={preview}
            error={previewError}
            onSelect={(row) => setChosen(row.version)}
            onPreview={(row) => ask.mutate(row)}
          />
        )}
      </Stack>
    </Container>
  );
}

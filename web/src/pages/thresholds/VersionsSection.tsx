/**
 * Список версий и раскрывающаяся подробность выбранной.
 *
 * Подробность стоит под самой строкой нарочно: вопросы «какие пороги у этой
 * версии» и «что изменится, если её применить» задают об одной конкретной
 * версии, и ответ, уехавший в другой угол экрана, приходится сопоставлять по
 * памяти.
 *
 * Раскрытие ведёт себя как на экране людей — общий хук `useFoldedChoice`, а не
 * копия поведения: нажатие на ту же версию сворачивает, нажатие на другую
 * сначала сворачивает открытую и только потом раскрывает новую.
 */
import { Alert, Collapse, Divider, Paper, Stack, Text, Title } from '@mantine/core';
import { useEffect } from 'react';

import { FOLD_MS, useFoldedChoice } from '../../app/foldedChoice';
import type { PreviewView, RulesetRow } from '../../api/types';

import { PreviewPanel } from './PreviewPanel';
import { RulesView } from './RulesView';
import { VersionsTable } from './VersionsTable';
import { readRules } from './rules';

interface Props {
  rows: RulesetRow[];
  /** Предпросмотр раскрытой версии: `null` — ещё считается или не спрашивали. */
  preview: PreviewView | null;
  busyVersion: string | null;
  error: string | null;
  /** Посчитать «что изменится». Зовётся раскрытием, а не кнопкой. */
  onPreview: (row: RulesetRow) => void;
  /** Раскрытая версия — её же показывает остальной экран. */
  onSelect: (version: string | null) => void;
}

export function VersionsSection({ rows, preview, busyVersion, error, onPreview, onSelect }: Props) {
  const { chosen, shown, choose } = useFoldedChoice('версия');
  const open = rows.find((row) => row.version === shown) ?? null;

  // Раскрытие — и есть вопрос «что изменится»: отдельная кнопка спрашивала то
  // же самое вторым нажатием. Считается один раз на раскрытие: предпросмотр
  // ничего не пишет, но проходит по всем проектам базы.
  useEffect(() => {
    onSelect(chosen);
    if (chosen === null) return;
    const row = rows.find((item) => item.version === chosen);
    if (row) onPreview(row);
    // Зависимость только от выбранной версии: список приезжает тем же
    // запросом и меняется вместе с ним, а пересчитывать предпросмотр на каждое
    // обновление списка значило бы считать его на каждом фоновом перезапросе.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chosen]);

  return (
    <Paper className="glass" p="lg">
      <Stack gap="md">
        <Title order={4}>Версии</Title>
        <Text size="sm" c="dimmed">
          Нажмите на версию — под ней раскроются её пороги и то, что изменится, если считать по ней.
        </Text>

        <VersionsTable rows={rows} selected={chosen} onSelect={(row) => choose(row.version)} />

        {open && (
          <Collapse in={chosen === open.version} transitionDuration={FOLD_MS}>
            <Stack gap="md" data-version-details={open.version}>
              <Divider />
              <Title order={5}>
                Пороги версии {open.version}
                {open.is_active ? ' — действующей' : ''}
              </Title>
              <RulesView rules={readRules(open.payload)} />

              <Divider />
              <Title order={5}>Что изменится</Title>
              {error && (
                <Alert color="red" variant="light">
                  <Text size="sm">{error}</Text>
                </Alert>
              )}
              {busyVersion === open.version && <Text size="sm">Считаем последствия…</Text>}
              {preview && busyVersion === null && <PreviewPanel preview={preview} />}
            </Stack>
          </Collapse>
        )}
      </Stack>
    </Paper>
  );
}

/**
 * Правка порогов: четыре шага, и каждый назван.
 *
 * Правка → сохранение версии → предпросмотр → применение. Сохранение не
 * применяет: иначе вся база переложилась бы по группам до того, как кто-то
 * посмотрел последствия. Предпросмотр после сохранения считается сам — это тот
 * самый цикл, которого требует ТЗ: «правишь цифру — видишь, кто сменит группу».
 */
import { Alert, Button, Paper, Stack, Text, Title } from '@mantine/core';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';

import { activateRuleset, previewRuleset, recalcRuleset, saveRuleset } from '../../api/thresholds';
import type { PreviewView, RecalcView, RulesetRow } from '../../api/types';
import { failureText } from '../cases/failure';

import { ApplyPanel } from './ApplyPanel';
import { ThresholdsForm } from './ThresholdsForm';
import type { FormValues } from './form';
import { missingRequired, payloadFrom, valuesFrom } from './form';

/** Начало правки или сама форма: до нажатия кнопки поля не показываются —
 *  пустая форма поверх утверждённых порогов читается как «их нет». */
function FormBlock({
  base,
  values,
  saving,
  onStart,
  onChange,
  onSave,
}: {
  base: RulesetRow;
  values: FormValues | null;
  saving: boolean;
  onStart: () => void;
  onChange: (patch: Partial<FormValues>) => void;
  onSave: (values: FormValues) => void;
}) {
  if (values === null) {
    return (
      <>
        <Text size="sm" c="dimmed">
          Правка — это всегда новая версия: прежняя остаётся, потому что на неё ссылаются вынесенные
          вердикты. Поля заполнятся значениями версии {base.version}.
        </Text>
        <Button onClick={onStart}>Править пороги</Button>
      </>
    );
  }
  // Пустое поле там, где сервер ждёт число, — это `422` после сохранения.
  // Сказать заранее дешевле, чем показать отказ и заставить искать поле.
  const empty = missingRequired(values);
  return (
    <>
      <ThresholdsForm values={values} onChange={onChange} />
      {empty.length > 0 && (
        <Alert color="yellow" variant="light">
          <Text size="sm">Эти поля обязательны, их нельзя оставить пустыми:</Text>
          <Text size="xs">{empty.join('; ')}</Text>
        </Alert>
      )}
      <Button
        loading={saving}
        disabled={values.version.trim() === '' || empty.length > 0}
        onClick={() => onSave(values)}
      >
        Сохранить версию и посмотреть последствия
      </Button>
    </>
  );
}

export function EditSection({ base, onChanged }: { base: RulesetRow; onChanged: () => void }) {
  const [values, setValues] = useState<FormValues | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [active, setActive] = useState(false);
  const [preview, setPreview] = useState<PreviewView | null>(null);
  const [recalcReport, setRecalcReport] = useState<RecalcView | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async (form: FormValues) => {
      const row = await saveRuleset(form.version, form.note, payloadFrom(base.payload, form));
      // Предпросмотр сразу за сохранением: человек правил цифру ради ответа
      // «кто сменит группу», и второе нажатие здесь ничего не добавляет.
      return { row, preview: await previewRuleset(row.version) };
    },
    onMutate: () => {
      setError(null);
      setPreview(null);
      setRecalcReport(null);
    },
    onSuccess: ({ row, preview: report }) => {
      setSaved(row.version);
      setActive(row.is_active);
      setPreview(report);
      onChanged();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'версия не сохранена')),
  });

  const apply = useMutation({
    mutationFn: (version: string) => activateRuleset(version),
    onSuccess: () => {
      setActive(true);
      setConfirming(false);
      onChanged();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'версия не применена')),
  });

  const again = useMutation({
    mutationFn: (version: string) => recalcRuleset(version),
    onSuccess: (report) => {
      setRecalcReport(report);
      onChanged();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'пересчёт не прошёл')),
  });

  return (
    <Paper className="glass" p="lg">
      <Stack gap="md">
        <Title order={4}>Правка порогов</Title>

        <FormBlock
          base={base}
          values={values}
          saving={save.isPending}
          onStart={() => setValues(valuesFrom(base.payload))}
          onChange={(patch) => setValues(values === null ? null : { ...values, ...patch })}
          onSave={(form) => save.mutate(form)}
        />

        {error && (
          <Alert color="red" variant="light">
            <Text size="sm">{error}</Text>
          </Alert>
        )}

        {saved && (
          <ApplyPanel
            version={saved}
            active={active}
            preview={preview}
            recalc={recalcReport}
            confirming={confirming}
            applying={apply.isPending}
            recalculating={again.isPending}
            onApply={() => (confirming ? apply.mutate(saved) : setConfirming(true))}
            onRecalc={() => again.mutate(saved)}
          />
        )}
      </Stack>
    </Paper>
  );
}

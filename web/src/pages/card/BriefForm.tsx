/**
 * Форма брифа: пункты шаблона по разделам и флажок NDA.
 *
 * Поля — родные (`NativeSelect`, `Textarea`): всплывающие списки Mantine в jsdom
 * разворачиваются секундами (урок L76). Уходит только изменённое: пустая строка
 * очищает пункт, неназванный не трогается. Отказ сервера называет поле словами,
 * и форма остаётся открытой — исправить и сохранить снова.
 *
 * Пустой пункт, который сервис заполняет сам, показывает его значение в самом поле —
 * пунктом «Сервис подставит: …» вместо «не выбрано» у списка и серой подсказкой у текста
 * (владелец 14.10.2026, снимок формы: «поля, которые должны быть заполнены автоматически,
 * не заполнены»). Это не значение поля: иначе сохранение записало бы вывод сервиса как
 * запись специалиста, и исправленное правило не дошло бы до этого брифа (инвариант 10).
 */
import {
  Alert,
  Button,
  Checkbox,
  Group,
  NativeSelect,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { saveBrief } from '../../api/brief';
import type { BriefCatalog, BriefField, BriefView, ProjectCard } from '../../api/types';
import { failureText } from '../cases/failure';

import { bySection, changes } from './briefValues';

interface Props {
  projectId: number;
  catalog: BriefCatalog;
  brief: Record<string, string>;
  /** Что сервис подставляет у пустых пунктов этого проекта (`brief_known`). */
  known: Record<string, string>;
  nda: boolean;
  onDone: () => void;
}

export function BriefForm({ projectId, catalog, brief, known, nda, onDone }: Props) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string>>(brief);
  const [closed, setClosed] = useState(nda);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      saveBrief(projectId, {
        fields: changes(brief, draft),
        ...(closed !== nda ? { nda: closed } : {}),
      }),
    onMutate: () => setError(null),
    onSuccess: (view: BriefView) => {
      // Карточка обновляется ответом, а не перезапросом: графики, кейс и окно
      // удаления живут на своих ключах, и перечитывать их незачем.
      queryClient.setQueryData<ProjectCard>(['project', projectId], (card) =>
        card
          ? { ...card, brief: view.fields, project: { ...card.project, publishable: !view.nda } }
          : card,
      );
      // Подстановка сервиса у пустых пунктов (`brief_known`) зависит от записанного:
      // очищенный пункт её получает, срез «По этапам» снимает период 1. Перечитывается
      // только сама карточка (`exact`) — графики на своих ключах не трогаются.
      void queryClient.invalidateQueries({ queryKey: ['project', projectId], exact: true });
      // Список проектов показывает «публикацию» — он узнаёт про NDA сам.
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
      onDone();
    },
    onError: (failure: unknown) => setError(failureText(failure, 'бриф не сохранён')),
  });

  const set = (key: string, value: string) => setDraft((current) => ({ ...current, [key]: value }));

  return (
    <Stack gap="md">
      <Checkbox
        label="Непубличный проект (NDA): домен и клиента в тексте кейса не раскрывать"
        checked={closed}
        onChange={(event) => setClosed(event.currentTarget.checked)}
      />
      {bySection(catalog).map(([section, fields]) => (
        <Stack gap="xs" key={section}>
          <Title order={5}>{section}</Title>
          {fields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={draft[field.key] ?? ''}
              auto={autoText(field, known)}
              onChange={(value) => set(field.key, value)}
            />
          ))}
        </Stack>
      ))}
      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}
      <Group>
        <Button onClick={() => save.mutate()} loading={save.isPending}>
          Сохранить бриф
        </Button>
        <Button variant="default" onClick={onDone} disabled={save.isPending}>
          Отмена
        </Button>
      </Group>
    </Stack>
  );
}

/** Что показать в пустом пункте, который сервис заполняет сам: значение проекта, а нет его — откуда. */
function autoText(field: BriefField, known: Record<string, string>): string | undefined {
  if (!field.autofill) return undefined;
  const value = known[field.key];
  return value ? `Сервис подставит: ${value}` : `Сервис: ${field.autofill}`;
}

interface FieldProps {
  field: BriefField;
  value: string;
  /** Пустое значение — за сервисом: что он подставит. */
  auto: string | undefined;
  onChange: (value: string) => void;
}

function FieldInput({ field, value, auto, onChange }: FieldProps) {
  if (field.kind === 'choice') {
    return (
      <NativeSelect
        label={field.label}
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        data={[
          { value: '', label: auto ?? 'не выбрано' },
          ...field.choices.map((choice) => ({ value: choice.key, label: choice.label })),
        ]}
      />
    );
  }
  if (field.kind === 'long_text') {
    return (
      <Textarea
        label={field.label}
        placeholder={auto}
        value={value}
        minRows={2}
        maxLength={field.max_len}
        onChange={(event) => onChange(event.currentTarget.value)}
      />
    );
  }
  return (
    <TextInput
      label={field.label}
      value={value}
      type={field.kind === 'link' ? 'url' : 'text'}
      maxLength={field.max_len}
      placeholder={auto ?? (field.kind === 'link' ? 'https://drive.google.com/…' : undefined)}
      onChange={(event) => onChange(event.currentTarget.value)}
    />
  );
}

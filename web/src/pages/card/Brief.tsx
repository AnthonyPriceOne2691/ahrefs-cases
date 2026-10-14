/**
 * Бриф для копирайтера на карточке: пункты шаблона кейса по разделам.
 *
 * Половину пунктов знает только специалист, который вёл проект, — их здесь и
 * заполняют (команда агентства 07.10.2026). Пустой пункт подписан «заполняет
 * специалист», как на листе: копирайтер видит пробел, а не пропуск.
 *
 * NDA — флажок проекта: домен и клиента в тексте кейса раскрывать нельзя.
 * Каталог пунктов — с сервера (`/api/brief-fields`), экран его не повторяет.
 * Скрины — часть брифа (в PDF это его раздел), их блок стоит сразу за пунктами.
 */
import { Alert, Anchor, Button, Group, Paper, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { fetchBriefFields } from '../../api/brief';
import type { BriefCatalog, BriefField, ProjectCard } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { failureText } from '../cases/failure';
import { plural } from '../format';

import { BriefForm } from './BriefForm';
import { EMPTY, bySection, shown } from './briefValues';
import { Screens } from './Screens';

interface Props {
  projectId: number;
  /** Карточка целиком, как у шапки: бриф, подстановка из файла (Z58) и NDA — её части. */
  card: ProjectCard;
}

export function Brief({ projectId, card }: Props) {
  const brief = card.brief ?? {};
  const known = card.brief_known ?? {};
  const nda = !card.project.publishable;
  const { can } = useAuth();
  const [editing, setEditing] = useState(false);
  const catalog = useQuery({
    queryKey: ['brief-fields'],
    queryFn: fetchBriefFields,
    staleTime: Infinity,
  });

  return (
    <>
      <Paper className="glass" p="lg">
        <Stack gap="sm">
          <Group justify="space-between">
            <Title order={3}>Бриф для копирайтера</Title>
            {can('edit_briefs') && catalog.data && !editing && (
              <Button variant="light" onClick={() => setEditing(true)}>
                Заполнить бриф
              </Button>
            )}
          </Group>
          <NdaLine nda={nda} />
          {catalog.isPending && <Text size="sm">Загружаем пункты брифа…</Text>}
          {catalog.isError && (
            <Text size="sm" c="dimmed">
              Пункты брифа не загрузились: {failureText(catalog.error, catalog.error.message)}
            </Text>
          )}
          {catalog.data &&
            (editing ? (
              <BriefForm
                projectId={projectId}
                catalog={catalog.data}
                brief={brief}
                known={known}
                nda={nda}
                onDone={() => setEditing(false)}
              />
            ) : (
              <BriefRead catalog={catalog.data} brief={brief} known={known} />
            ))}
        </Stack>
      </Paper>
      <Screens projectId={projectId} />
    </>
  );
}

function NdaLine({ nda }: { nda: boolean }) {
  if (!nda) {
    return (
      <Text size="sm" c="dimmed">
        Публичный проект: домен и клиента в тексте кейса называть можно.
      </Text>
    );
  }
  return (
    <Alert color="orange" variant="light" p="xs">
      <Text size="sm">
        Непубличный проект (NDA): домен и название клиента в тексте кейса не раскрывать.
      </Text>
    </Alert>
  );
}

interface ReadProps {
  catalog: BriefCatalog;
  brief: Record<string, string>;
  known: Record<string, string>;
}

function BriefRead({ catalog, brief, known }: ReadProps) {
  // Пустой бриф не разворачивается двадцатью двумя пунктами: иначе цифры и «Почему эта
  // группа» уезжают далеко вниз (решение владельца 07.10.2026). Частично заполненный
  // показывает все пункты, пустые — подстановкой сервиса, как лист PDF.
  const sections = bySection(catalog);
  const listed = sections.flatMap(([, fields]) => fields);
  if (!listed.some((field) => brief[field.key])) {
    return <EmptyBrief listed={listed} known={known} />;
  }
  return (
    <Stack gap="md">
      {sections.map(([section, fields]) => (
        <Stack gap={4} key={section}>
          <Title order={5}>{section}</Title>
          <FieldRows fields={fields} value={(key) => brief[key] || known[key]} />
        </Stack>
      ))}
    </Stack>
  );
}

const POINTS = ['пункт', 'пункта', 'пунктов'] as const;

/**
 * Пустой бриф. До 14.10.2026 — одна строка «пунктов для специалиста: 22», и владелец,
 * зайдя в бриф после пересборки, не увидел того, что сервис заполнил сам: «поля, которые
 * должны быть заполнены автоматически, — не заполнены». Теперь — пункты, которые сервис
 * заполняет сам (`autofill` каталога), со значением этого проекта (`brief_known`), а нет
 * его — серым, откуда сервис его берёт; остальное — одной строкой. Число в ней — пункты
 * без `autofill`, а не длина каталога (Z64, L260). Каталог без `autofill` — прежняя строка.
 */
function EmptyBrief({ listed, known }: { listed: BriefField[]; known: Record<string, string> }) {
  const auto = listed.filter((field) => field.autofill);
  if (auto.length === 0) {
    return (
      <Text size="sm" c="dimmed" data-brief-empty>
        Бриф ещё не заполнен — пунктов для специалиста: {listed.length}
      </Text>
    );
  }
  return (
    <Stack gap={4} data-brief-auto>
      <Text size="sm" fw={500}>
        Сервис заполняет сам, пока пункт пуст:
      </Text>
      <FieldRows
        fields={auto}
        value={(key) => known[key]}
        missing={(field) => field.autofill ?? EMPTY}
      />
      <Text size="sm" c="dimmed" data-brief-empty>
        Остальные {plural(listed.length - auto.length, POINTS)} заполняет специалист.
      </Text>
    </Stack>
  );
}

interface RowsProps {
  fields: BriefField[];
  value: (key: string) => string | undefined;
  /** Что писать у пункта без значения; по умолчанию — «заполняет специалист». */
  missing?: (field: BriefField) => string;
}

function FieldRows({ fields, value, missing }: RowsProps) {
  return (
    <Table withRowBorders={false} verticalSpacing={4}>
      <Table.Tbody>
        {fields.map((field) => (
          <Table.Tr key={field.key}>
            <Table.Td w="40%">
              <Text size="sm" c="dimmed">
                {field.label}
              </Text>
            </Table.Td>
            <Table.Td>
              <Value field={field} value={value(field.key)} missing={missing?.(field)} />
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

interface ValueProps {
  field: BriefField;
  value: string | undefined;
  missing?: string | undefined;
}

function Value({ field, value, missing = EMPTY }: ValueProps) {
  if (!value) {
    return (
      <Text size="sm" c="dimmed" fs="italic">
        {missing}
      </Text>
    );
  }
  if (field.kind === 'link') {
    return (
      <Anchor href={value} target="_blank" rel="noopener noreferrer" size="sm">
        {value}
      </Anchor>
    );
  }
  return (
    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
      {shown(field, value)}
    </Text>
  );
}

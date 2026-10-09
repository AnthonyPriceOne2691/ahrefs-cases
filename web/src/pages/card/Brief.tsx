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
  // Пустой бриф — одна строка, а не двадцать пять «заполняет специалист»: иначе цифры и
  // «Почему эта группа» уезжают далеко вниз (решение владельца 07.10.2026). Частично
  // заполненный показывает пробелы, как прежде.
  const sections = bySection(catalog);
  const listed = sections.flatMap(([, fields]) => fields);
  if (!listed.some((field) => brief[field.key])) {
    return (
      <Text size="sm" c="dimmed" data-brief-empty>
        Бриф ещё не заполнен — пунктов для специалиста: {listed.length}
      </Text>
    );
  }
  return (
    <Stack gap="md">
      {sections.map(([section, fields]) => (
        <Stack gap={4} key={section}>
          <Title order={5}>{section}</Title>
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
                    {/* Пустой пункт — то, что знает файл, как на листе PDF; пустой бриф
                        целиком по-прежнему одна строка: в нём специалист ещё ничего не писал. */}
                    <Value field={field} value={brief[field.key] || known[field.key]} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      ))}
    </Stack>
  );
}

function Value({ field, value }: { field: BriefField; value: string | undefined }) {
  if (!value) {
    return (
      <Text size="sm" c="dimmed" fs="italic">
        {EMPTY}
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

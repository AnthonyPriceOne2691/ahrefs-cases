/**
 * Бриф для копирайтера на карточке: пункты шаблона кейса по разделам.
 *
 * Половину пунктов знает только специалист, который вёл проект, — их здесь и
 * заполняют (команда агентства 07.10.2026). Пустой пункт подписан «заполняет
 * специалист», как на листе: копирайтер видит пробел, а не пропуск.
 *
 * NDA — флажок проекта: домен и клиента в тексте кейса раскрывать нельзя.
 * Каталог пунктов — с сервера (`/api/brief-fields`), экран его не повторяет.
 */
import { Alert, Anchor, Button, Group, Paper, Stack, Table, Text, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { fetchBriefFields } from '../../api/brief';
import type { BriefCatalog, BriefField } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { failureText } from '../cases/failure';

import { BriefForm } from './BriefForm';
import { EMPTY, bySection, shown } from './briefValues';

interface Props {
  projectId: number;
  brief: Record<string, string>;
  nda: boolean;
}

export function Brief({ projectId, brief, nda }: Props) {
  const { can } = useAuth();
  const [editing, setEditing] = useState(false);
  const catalog = useQuery({
    queryKey: ['brief-fields'],
    queryFn: fetchBriefFields,
    staleTime: Infinity,
  });

  return (
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
            <BriefRead catalog={catalog.data} brief={brief} />
          ))}
      </Stack>
    </Paper>
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

function BriefRead({ catalog, brief }: { catalog: BriefCatalog; brief: Record<string, string> }) {
  return (
    <Stack gap="md">
      {bySection(catalog).map(([section, fields]) => (
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
                    <Value field={field} value={brief[field.key]} />
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

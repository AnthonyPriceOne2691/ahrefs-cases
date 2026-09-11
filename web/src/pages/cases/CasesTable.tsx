/**
 * Библиотека кейсов: что собрано и что из этого можно отдавать.
 *
 * Две колонки здесь не для красоты. **Версия** — потому что пересборка не
 * затирает прежний кейс, а добавляет следующий: рядом живут два PDF по одному
 * домену, и отдать нужно свежий. **Публикация** — потому что кейс
 * анонимизированного проекта нельзя называть именем клиента, и узнавать это,
 * открыв PDF, поздно.
 */
import { Badge, Button, Table, Text } from '@mantine/core';

import type { CaseRow } from '../../api/types';

const STATUS_COLOR: Record<string, string> = {
  draft: 'gray',
  built: 'teal',
  published: 'blue',
};

function moment(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

interface Props {
  rows: CaseRow[];
  /** Кейс, который сейчас скачивается: кнопка у него занята, остальные живы. */
  busyId: number | null;
  onDownload: (row: CaseRow) => void;
}

export function CasesTable({ rows, busyId, onDownload }: Props) {
  return (
    <Table.ScrollContainer minWidth={820}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Домен</Table.Th>
            <Table.Th>Версия</Table.Th>
            <Table.Th>Собран</Table.Th>
            <Table.Th>Статус</Table.Th>
            <Table.Th>Публикация</Table.Th>
            <Table.Th>Файл</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={row.id} data-case={row.id}>
              <Table.Td>{row.domain}</Table.Td>
              <Table.Td>{row.version}</Table.Td>
              <Table.Td>{moment(row.created_at)}</Table.Td>
              <Table.Td>
                <Badge variant="light" color={STATUS_COLOR[row.status] ?? 'gray'}>
                  {row.status}
                </Badge>
              </Table.Td>
              <Table.Td>
                {/* Метка говорит следствие, а не флаг: «anonymized: true» верно
                    и бесполезно тому, кто решает, что отправить клиенту. */}
                {row.anonymized ? (
                  <Badge variant="light" color="orange" data-anonymized="yes">
                    домен скрыт
                  </Badge>
                ) : (
                  <Badge variant="light" color="teal" data-anonymized="no">
                    можно публиковать
                  </Badge>
                )}
              </Table.Td>
              <Table.Td>
                {row.filename ? (
                  <Button
                    size="compact-sm"
                    variant="light"
                    loading={busyId === row.id}
                    onClick={() => onDownload(row)}
                  >
                    Скачать PDF
                  </Button>
                ) : (
                  // Кейс есть, файла нет: так бывает, когда каталог выгрузки
                  // почистили. Неактивная кнопка молчала бы о причине.
                  <Text size="xs" c="dimmed">
                    файла нет — пересоберите кейсы
                  </Text>
                )}
                {row.filename && (
                  <Text size="xs" c="dimmed">
                    {row.filename}
                  </Text>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

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
import { caseWord } from '../status';

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
            {/* Домен слева, остальное по центру: домен — имя строки, его
                читают сверху вниз, и рваный левый край мешал бы искать
                глазами. Прочие колонки короткие и одной природы. */}
            <Table.Th>Домен</Table.Th>
            <Table.Th ta="center">Версия</Table.Th>
            <Table.Th ta="center">Собран</Table.Th>
            <Table.Th ta="center">Статус</Table.Th>
            <Table.Th ta="center">Публикация</Table.Th>
            <Table.Th ta="center">Файл</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row) => (
            <Table.Tr key={row.id} data-case={row.id}>
              <Table.Td>{row.domain}</Table.Td>
              <Table.Td ta="center">{row.version}</Table.Td>
              <Table.Td ta="center">{moment(row.created_at)}</Table.Td>
              <Table.Td ta="center">
                <Badge
                  variant="light"
                  color={STATUS_COLOR[row.status] ?? 'gray'}
                  data-status={row.status}
                >
                  {caseWord(row.status)}
                </Badge>
              </Table.Td>
              <Table.Td ta="center">
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
              <Table.Td ta="center">
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

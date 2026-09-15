/**
 * Библиотека кейсов: что собрано и что из этого можно отдавать.
 *
 * Две колонки здесь не для красоты. **Версия** — потому что пересборка не
 * затирает прежний кейс, а добавляет следующий: рядом живут два PDF по одному
 * домену, и отдать нужно свежий. **Публикация** — потому что кейс
 * анонимизированного проекта нельзя называть именем клиента, и узнавать это,
 * открыв PDF, поздно.
 */
import { Badge, Button, Checkbox, Table, Text } from '@mantine/core';

import type { CaseRow } from '../../api/types';
import { caseWord } from '../status';

import type { Selection } from './selection';
import { takeable } from './selection';

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
  selection: Selection;
}

/** Галочка «выбрать всё» считается по строкам С ФАЙЛОМ: иначе на странице, где
 *  у половины кейсов файла нет, она оставалась бы полупустой навсегда и
 *  читалась как поломка. */
function SelectAll({ rows, selection }: { rows: CaseRow[]; selection: Selection }) {
  const pickable = takeable(rows);
  const picked = pickable.filter((row) => selection.has(row.id)).length;
  return (
    <Checkbox
      aria-label="выбрать все кейсы на странице"
      disabled={pickable.length === 0}
      checked={pickable.length > 0 && picked === pickable.length}
      indeterminate={picked > 0 && picked < pickable.length}
      onChange={(event) => selection.pickAll(event.currentTarget.checked)}
    />
  );
}

/** Метка говорит следствие, а не флаг: «anonymized: true» верно и бесполезно
 *  тому, кто решает, что отправить клиенту. */
function Publishing({ anonymized }: { anonymized: boolean }) {
  return anonymized ? (
    <Badge variant="light" color="orange" data-anonymized="yes">
      домен скрыт
    </Badge>
  ) : (
    <Badge variant="light" color="teal" data-anonymized="no">
      можно публиковать
    </Badge>
  );
}

export function CasesTable({ rows, busyId, onDownload, selection }: Props) {
  return (
    <Table.ScrollContainer minWidth={820}>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            {/* Домен слева, остальное по центру: домен — имя строки, его
                читают сверху вниз, и рваный левый край мешал бы искать
                глазами. Прочие колонки короткие и одной природы. */}
            <Table.Th w={44}>
              <SelectAll rows={rows} selection={selection} />
            </Table.Th>
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
              <Table.Td>
                <Checkbox
                  aria-label={`выбрать кейс ${row.domain}`}
                  disabled={row.filename === null}
                  checked={selection.has(row.id)}
                  onChange={(event) => selection.pick(row.id, event.currentTarget.checked)}
                />
              </Table.Td>
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
                <Publishing anonymized={row.anonymized} />
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

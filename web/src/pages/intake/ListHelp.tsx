/**
 * Справка о списке: каким он должен быть — у поля файла и у поля ссылки.
 *
 * Вопрос «что должно быть внутри» задают, уже держа список в руках, каким бы
 * способом его ни давали, поэтому знак «?» стоит у обоих полей. Колонки у двух
 * способов одни и те же, и карточка одна (`ListCard`); различается только
 * первый абзац: у ссылки — доступ и лист из gid, у файла — форматы, лист книги,
 * разделитель и кодировка.
 *
 * Колонки — данные (`listFormat.json`), а не разметка: их читают обе карточки и
 * фильтр выбора файла, а `tests/test_intake_list_format.py` сверяет их с
 * приёмом (урок L123). Словарь внутри справки о таблице ждал второго
 * читателя (L97) — второй пришёл.
 *
 * `HoverCard`, а не `Tooltip`: десять колонок с примерами — таблица, а не фраза.
 */
import { ActionIcon, Code, HoverCard, List, Stack, Table, Text } from '@mantine/core';
import type { ReactNode } from 'react';

import format from './listFormat.json';

export interface ListColumn {
  name: string;
  what: string;
  example?: string;
  mayBeEmpty?: boolean;
}

/** Обязательные колонки — те же, что требует приём (`intake/validate.py`). */
export const LIST_COLUMNS: readonly ListColumn[] = format.columns;
const OPTIONAL_COLUMNS: readonly ListColumn[] = format.optional;

/** Фильтр выбора файла и предел размера — из тех же данных, что подсказка. */
export const FILE_ACCEPT = format.fileSuffixes.join(',');
export const MAX_MEGABYTES = format.maxMegabytes;

export const SHEET_ACCESS =
  'Авторизация не нужна: сервис читает CSV-экспорт таблицы. Откройте доступ «по ссылке» — ' +
  'приватную таблицу Google отдаёт страницей входа, и сервис скажет, что доступа нет.';

export const FILE_FORMAT =
  `XLSX (или XLSM) либо CSV, до ${MAX_MEGABYTES} МБ. В книге читается только ` +
  'первый лист — список должен лежать на нём.';

export const FILE_CSV =
  'CSV — в UTF-8 или Windows-1251 (так сохраняет Excel); разделитель — запятая, точка с ' +
  'запятой или табуляция, его находим по шапке.';

/** Кусок ссылки не рвётся переносом: «?» на одной строке и «usp=sharing» на
 *  другой читались как два разных совета (замер в Chrome). */
const WHOLE = { whiteSpace: 'nowrap' } as const;

function ListCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <HoverCard width={460} shadow="md" position="right-start" withArrow openDelay={150}>
      <HoverCard.Target>
        <ActionIcon size="sm" radius="xl" variant="light" color="blue" aria-label={label}>
          ?
        </ActionIcon>
      </HoverCard.Target>
      <HoverCard.Dropdown>
        <Stack gap="xs">
          <Text size="sm" fw={600}>
            {label.charAt(0).toUpperCase() + label.slice(1)}
          </Text>
          {children}
          <Text size="xs">
            Первая строка — шапка с именами колонок латиницей, колонки одни и те же у файла и у
            таблицы по ссылке. Список без нужных колонок, пустой или из одной шапки не принимается
            целиком — сервис назовёт, чего не хватает. Строки с браком в подходящем списке попадут в
            отчёт с номером и причиной, остальные примутся.
          </Text>

          <Table withRowBorders={false} verticalSpacing={2}>
            <Table.Tbody>
              {LIST_COLUMNS.map((column) => (
                <Table.Tr key={column.name}>
                  <Table.Td>
                    <Text size="xs" ff="monospace" data-column>
                      {column.name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">
                      {column.mayBeEmpty ? `${column.what}, можно пустым` : column.what}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">
                      {column.example}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <List size="xs" spacing={2}>
            <List.Item>
              Даты: <b>2024-12-01</b>, 01.12.2024, 01/12/2024, 2024/12/01.
            </List.Item>
            <List.Item>
              <b>publishable</b>: да/нет, yes/no, true/false, 1/0, +/-. Пустое читается как «нет».
            </List.Item>
            {OPTIONAL_COLUMNS.map((column) => (
              <List.Item key={column.name}>
                Необязательная <b>{column.name}</b> — {column.what}.
              </List.Item>
            ))}
          </List>
        </Stack>
      </HoverCard.Dropdown>
    </HoverCard>
  );
}

export function SheetHelp() {
  return (
    <ListCard label="какой должна быть таблица">
      <Text size="xs">{SHEET_ACCESS}</Text>
      <Text size="xs">
        Ссылку можно вставлять как есть: <Code style={WHOLE}>/edit#gid=…</Code> или с{' '}
        <Code style={WHOLE}>?usp=sharing</Code> — нужный лист берётся из gid.
      </Text>
    </ListCard>
  );
}

export function FileHelp() {
  return (
    <ListCard label="каким должен быть файл">
      <Text size="xs">{FILE_FORMAT}</Text>
      <Text size="xs">{FILE_CSV}</Text>
    </ListCard>
  );
}

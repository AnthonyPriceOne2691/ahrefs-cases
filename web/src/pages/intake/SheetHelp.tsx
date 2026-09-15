/**
 * Справка о таблице: какие колонки нужны и какой доступ.
 *
 * Стоит у поля ссылки, потому что там вопрос и возникает: файл человек обычно
 * собирает по образцу, а ссылку присылает отдел — и «что должно быть внутри»
 * спрашивают, уже держа таблицу в руках. Колонки при этом **одни и те же** для
 * обоих способов, и карточка говорит об этом прямо.
 *
 * `HoverCard`, а не `Tooltip`: подсказка в одну строку сюда не помещается —
 * десять колонок с примерами это таблица, а не фраза.
 *
 * Текст живёт отдельными данными (`SHEET_COLUMNS`), а не разметкой: его
 * проверяет оракул, не открывая всплывающую карточку — попапы Mantine в jsdom
 * разворачиваются секундами (грабли Ф6).
 */
import { ActionIcon, Anchor, HoverCard, List, Stack, Table, Text } from '@mantine/core';

/** Обязательные колонки — те же, что требует приём (`intake/validate.py`). */
export const SHEET_COLUMNS: readonly { name: string; what: string; example: string }[] = [
  { name: 'domain', what: 'домен проекта', example: 'example.com' },
  { name: 'period_start', what: 'начало работ', example: '2024-12-01' },
  { name: 'period_end', what: 'конец работ', example: '2025-12-01' },
  { name: 'niche', what: 'ниша', example: 'медицина' },
  { name: 'geo', what: 'страна, две буквы', example: 'RU' },
  { name: 'service_type', what: 'услуга', example: 'seo' },
  { name: 'work_volume', what: 'объём работ, можно пустым', example: '120' },
  { name: 'client', what: 'клиент', example: 'ООО «Ромашка»' },
  { name: 'owner', what: 'ответственный', example: 'Пётр' },
  { name: 'publishable', what: 'называть ли домен в кейсе', example: 'да' },
];

export const SHEET_ACCESS =
  'Авторизация не нужна: сервис читает CSV-экспорт таблицы. Откройте доступ «по ссылке» — ' +
  'приватную таблицу Google отдаёт страницей входа, и сервис скажет, что доступа нет.';

export function SheetHelp() {
  return (
    <HoverCard width={460} shadow="md" position="right-start" withArrow openDelay={150}>
      <HoverCard.Target>
        <ActionIcon
          size="sm"
          radius="xl"
          variant="light"
          color="blue"
          aria-label="какой должна быть таблица"
          data-sheet-help
        >
          ?
        </ActionIcon>
      </HoverCard.Target>
      <HoverCard.Dropdown>
        <Stack gap="xs">
          <Text size="sm" fw={600}>
            Какой должна быть таблица
          </Text>
          <Text size="xs">{SHEET_ACCESS}</Text>
          <Text size="xs">
            Первая строка — шапка с именами колонок латиницей. Те же колонки нужны и в файле
            XLSX/CSV. Строки без обязательных полей не отменяют загрузку: они попадут в отчёт с
            номером строки и причиной, остальные примутся.
          </Text>

          <Table withRowBorders={false} verticalSpacing={2}>
            <Table.Tbody>
              {SHEET_COLUMNS.map((column) => (
                <Table.Tr key={column.name}>
                  <Table.Td>
                    <Text size="xs" ff="monospace">
                      {column.name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs">{column.what}</Text>
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
              <b>publishable</b>: да/нет, yes/no, true/false, 1/0, +/−. Пустое читается как «нет».
            </List.Item>
            <List.Item>
              Необязательные: <b>target_mode</b> — как считать домен в Ahrefs (по умолчанию
              subdomains; prefix для раздела сайта, exact) — и <b>notes</b>.
            </List.Item>
          </List>

          <Text size="xs" c="dimmed">
            Ссылку можно вставлять как есть:{' '}
            <Anchor size="xs" href="#" onClick={(event) => event.preventDefault()}>
              /edit#gid=…
            </Anchor>{' '}
            или с ?usp=sharing — нужный лист берётся из gid.
          </Text>
        </Stack>
      </HoverCard.Dropdown>
    </HoverCard>
  );
}

/**
 * Отчёт о приёме списка: что взяли и что отклонили.
 *
 * Три числа показываются раздельно, потому что повторная загрузка того же файла
 * законна: «обновлено 93» и «принято 93» второй раз — разные новости.
 *
 * Отказы не сворачиваются в «7 ошибок»: ТЗ требует отчёт, по которому строку
 * можно найти и починить, а для этого нужны её номер и причина.
 */
import { Alert, Badge, Group, Stack, Table, Text, Title } from '@mantine/core';

import type { IntakeReport, RejectionRow } from '../../api/types';

const REASONS: Record<string, string> = {
  empty_domain: 'пустой домен',
  invalid_domain: 'домен не разобран',
  ip_address: 'вместо домена IP-адрес',
  empty_source: 'в источнике нет колонок',
  missing_field: 'пустое обязательное поле',
  missing_column: 'в файле нет колонки',
  bad_date: 'дата не разобрана',
  period_order: 'конец периода раньше начала',
  bad_geo: 'гео не двухбуквенный код',
  bad_enum: 'значение не из списка',
  bad_number: 'число не разобрано',
  bad_flag: 'флаг не «да»/«нет»',
  duplicate_in_source: 'домен встречается в файле дважды',
};

/** Код без перевода показывается как есть: новый код на сервере обязан быть
 *  виден человеку, а не превращаться в пустое место. */
function reasonText(code: string): string {
  return REASONS[code] ?? code;
}

export function IntakeOutcome({ report }: { report: IntakeReport }) {
  return (
    <Stack gap="sm">
      <Title order={4}>Принято из «{report.origin}»</Title>
      <Group gap="xs">
        <Badge size="lg" variant="light">
          принято {report.accepted}
        </Badge>
        <Badge size="lg" variant="light" color="teal">
          создано {report.created}
        </Badge>
        <Badge size="lg" variant="light" color="blue">
          обновлено {report.updated}
        </Badge>
        {report.rejected_rows > 0 && (
          <Badge size="lg" variant="light" color="red">
            отклонено строк {report.rejected_rows}
          </Badge>
        )}
        {report.notices.length > 0 && (
          <Badge size="lg" variant="light" color="yellow">
            с замечаниями {new Set(report.notices.map((item) => item.row_no)).size}
          </Badge>
        )}
      </Group>

      {report.accepted === 0 && report.rejected_rows === 0 && (
        <Alert color="yellow" variant="light">
          <Text size="sm">
            В источнике не нашлось ни одной строки. Проверьте, что список лежит на первом листе и у
            него есть строка заголовка.
          </Text>
        </Alert>
      )}

      {report.rejections.length > 0 && (
        <Rows title="Строки, которые не приняты" rows={report.rejections} />
      )}

      {report.notices.length > 0 && (
        <>
          <Text size="sm" data-testid="notices-note">
            Эти проекты{' '}
            <Text span fw={600}>
              приняты
            </Text>
            , но одну ячейку разобрать не удалось. Объём работ остался неизвестным — в кейсе блок
            «что сделали» просто не появится, а число не выдумывается.
          </Text>
          <Rows title="Принято с замечаниями" rows={report.notices} />
        </>
      )}
    </Stack>
  );
}

function Rows({ title, rows }: { title: string; rows: RejectionRow[] }) {
  return (
    <Table striped withTableBorder captionSide="top">
      <Table.Caption>{title}</Table.Caption>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Строка</Table.Th>
          <Table.Th>Поле</Table.Th>
          <Table.Th>Причина</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((item) => (
          <Table.Tr key={`${item.row_no}-${item.field}-${item.reason}`}>
            <Table.Td>{item.row_no}</Table.Td>
            <Table.Td>{item.field}</Table.Td>
            <Table.Td>
              {reasonText(item.reason)}
              {item.detail && <Text size="xs">{item.detail}</Text>}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

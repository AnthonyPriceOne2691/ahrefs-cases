/**
 * Условия вердикта — то, чего в кейсе нет вовсе.
 *
 * Кейс показывает результат клиенту, карточка объясняет сотруднику, **почему**
 * группа такая: какой факт с каким порогом сравнили и какое условие оказалось
 * решающим. Без этого число на экране приходится принимать на веру.
 */
import { Badge, Group, Stack, Table, Text, Title } from '@mantine/core';

import type { ReasonRow } from '../../api/types';
import { num } from '../format';
import { conditionsTitle } from '../groups';

/**
 * Условия, разложенные по группам, к которым они относятся.
 *
 * Ключ правила выглядит как `good.kw_top10_pct`. До 15.09.2026 он печатался
 * целиком, 15.09 его заменила колонка «Группа» — и она читалась ещё хуже:
 * у `cleverfiles.com` одиннадцать условий, шесть подряд со словом «хороший»,
 * потом пять со словом «средний», а у прошедшего в хорошие — шесть одинаковых
 * строк подряд. Владелец: «даже в плохих проектах выглядит странно» (Z26).
 *
 * Группа — свойство целого набора строк, а не каждой из них по отдельности,
 * поэтому она стала заголовком блока. Различать одинаковые формулировки с
 * разными порогами это по-прежнему позволяет: «рост органического трафика в
 * процентах» с порогом 100 стоит под «Условиями хорошего», с порогом 20 — под
 * «Условиями среднего».
 *
 * Условия вне групп (нет трафика, дыра в серии, непокупленные месяцы) идут
 * первым блоком: они решают, судить ли вообще, и относятся ко всему вердикту.
 */
function blocks(rows: ReasonRow[]): { group: string; rows: ReasonRow[] }[] {
  const byGroup = new Map<string, ReasonRow[]>();
  for (const row of rows) {
    const [prefix] = row.subject.split('.');
    const group = prefix && prefix !== row.subject ? prefix : '';
    byGroup.set(group, [...(byGroup.get(group) ?? []), row]);
  }
  // Порядок задан здесь, а не порядком строк вердикта: общие условия решают,
  // судить ли вообще, а «хороший» проверяется раньше «среднего».
  const order = ['', 'good', 'medium'];
  return [...byGroup.entries()]
    .sort(([a], [b]) => {
      const rank = (group: string) => (order.indexOf(group) + 1 || order.length + 1) - 1;
      return rank(a) - rank(b);
    })
    .map(([group, groupRows]) => ({ group, rows: groupRows }));
}

/**
 * Что стоит в колонке «Факт», когда факта нет.
 *
 * Прочерк означал два разных случая (Z25): историю метрики **не покупали** —
 * шаг 2 платится только кандидатам в кейсы — или купили, а Ahrefs ничего не
 * отдал. Заказчик спрашивает «вы не купили или не смогли?», и разница в
 * деньгах: докупить можно только первое. Причину знает сервер (журнал расхода
 * units), экран её называет словом; молчит сервер — остаётся прочерк.
 */
function factOf(row: ReasonRow): string {
  if (row.fact !== null) return num(row.fact);
  if (row.fact_missing === 'not_bought') return 'не покупали';
  if (row.fact_missing === 'no_data') return 'нет данных';
  return '—';
}

function ReasonsTable({ rows }: { rows: ReasonRow[] }) {
  return (
    <Table striped>
      <Table.Thead>
        {/* Условие — имя строки, его читают сверху вниз, и рваный левый край
            мешал бы искать глазами. Остальные колонки короткие и одной
            природы, поэтому по центру — то же правило, что в таблице
            кейсов. */}
        <Table.Tr>
          <Table.Th>Условие</Table.Th>
          <Table.Th ta="center">Факт</Table.Th>
          <Table.Th ta="center">Порог</Table.Th>
          <Table.Th ta="center">Итог</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((row) => (
          <Table.Tr key={`${row.subject}-${row.note}`} data-subject={row.subject}>
            <Table.Td>
              <Group gap="xs">
                <Text size="sm">{row.note || row.subject}</Text>
                {row.decisive && (
                  <Badge size="xs" variant="light" data-decisive="true">
                    решающее
                  </Badge>
                )}
              </Group>
            </Table.Td>
            <Table.Td ta="center" data-fact-missing={row.fact_missing ?? undefined}>
              {row.fact === null ? (
                <Text size="sm" c="dimmed">
                  {factOf(row)}
                </Text>
              ) : (
                factOf(row)
              )}
            </Table.Td>
            <Table.Td ta="center">{row.threshold === null ? '—' : num(row.threshold)}</Table.Td>
            <Table.Td ta="center" data-passed={row.passed}>
              {row.passed ? 'прошло' : 'не прошло'}
            </Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

export function Reasons({ rows }: { rows: ReasonRow[] }) {
  if (rows.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        Условия вердикта не записаны: версия порогов старше, чем эта запись.
      </Text>
    );
  }
  return (
    <Stack gap="lg">
      {blocks(rows).map((block) => (
        <Stack key={block.group || 'common'} gap="xs" data-conditions={block.group}>
          <Title order={5}>{conditionsTitle(block.group)}</Title>
          <ReasonsTable rows={block.rows} />
        </Stack>
      ))}
    </Stack>
  );
}

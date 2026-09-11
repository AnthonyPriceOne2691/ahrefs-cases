/**
 * Действующие пороги словами.
 *
 * Показывается и то, что **здесь не правится** — окна точек, нормализация:
 * скрытое поле читается как отсутствующее, а оно есть и на вердикты влияет.
 */
import { Alert, Badge, Divider, Group, List, Stack, Text, Title } from '@mantine/core';

import type { GroupRule, Rules } from './rules';
import { baselineWords, groupSentences } from './rules';

function GroupBlock({
  title,
  color,
  rule,
}: {
  title: string;
  color: string;
  rule: GroupRule | null;
}) {
  if (rule === null) {
    return (
      <Alert color="red" variant="light">
        <Text size="sm">Группы «{title}» в этой версии нет — классифицировать по ней нельзя.</Text>
      </Alert>
    );
  }
  return (
    <Stack gap="xs">
      <Badge variant="light" color={color} data-group={title}>
        {title}
      </Badge>
      <List size="sm" spacing={4}>
        {groupSentences(rule).map((line) => (
          <List.Item key={line}>{line}</List.Item>
        ))}
      </List>
    </Stack>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <Text size="sm" c="dimmed">
        {label}:
      </Text>
      <Text size="sm">{value}</Text>
    </Group>
  );
}

/** Ноль в этих полях означает «условие выключено», а не «порог равен нулю». */
function offOrValue(value: number | null, render: (v: number) => string): string {
  if (value === null) return 'не задано';
  return value === 0 ? 'не задано' : render(value);
}

export function RulesView({ rules }: { rules: Rules }) {
  return (
    <Stack gap="md">
      <GroupBlock title="хороший" color="teal" rule={rules.good} />
      <GroupBlock title="средний" color="yellow" rule={rules.medium} />

      <Divider />

      <Title order={5}>Когда классифицировать вообще нельзя</Title>
      <Fact
        label="Не раньше, чем после старта"
        value={rules.minMonthsAfterStart === null ? '—' : `${rules.minMonthsAfterStart} мес.`}
      />
      <Fact
        label="Разрыв в рядах не больше"
        value={rules.maxGapMonths === null ? '—' : `${rules.maxGapMonths} мес.`}
      />
      <Fact
        label="Минимальный трафик точки Б"
        value={offOrValue(rules.minTrafficPointB, (v) => `${v.toLocaleString('ru-RU')} визитов`)}
      />
      <Fact
        label="Конец периода не ниже пика на"
        value={offOrValue(rules.endVsPeakMinPct, (v) => `${v} %`)}
      />

      <Divider />

      <Title order={5}>Как считаются точки А и Б</Title>
      <Text size="xs" c="dimmed">
        Эти значения меняют смысл самих данных, а не границу группы, — поэтому показаны, но здесь не
        правятся.
      </Text>
      <Fact
        label="Точка А — среднее за"
        value={rules.pointAMonths === null ? '—' : `${rules.pointAMonths} мес.`}
      />
      <Fact
        label="Точка Б — среднее за"
        value={rules.pointBMonths === null ? '—' : `${rules.pointBMonths} мес.`}
      />
      <Fact label="База отсчёта" value={baselineWords(rules.baseline)} />
      <Fact
        label="Месяцев до старта в базе"
        value={rules.preStartMonths === null ? '—' : `${rules.preStartMonths}`}
      />

      {rules.normalizeAfterMonths !== null && rules.normalizeAfterMonths > 0 && (
        // Ненулевое значение отказывает на разборе: блок не реализован, формулы
        // от заказчика нет. Версия с ним не пройдёт сохранение — говорим сразу.
        <Alert color="orange" variant="light">
          <Text size="sm">
            Нормализация на длительность работ ({rules.normalizeAfterMonths} мес.) не реализована:
            формулы от заказчика нет. Считать по этой версии сервис откажется.
          </Text>
        </Alert>
      )}
    </Stack>
  );
}

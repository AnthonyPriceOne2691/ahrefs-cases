/**
 * Поля правки порогов.
 *
 * Подписи те же, что в просмотре: человек правит то, что читал предложением, и
 * разные слова в этих двух местах означали бы, что правят не то, что смотрели.
 *
 * Пустое поле — «не задано», а не ноль: `NumberInput` отдаёт пустую строку, и
 * она доезжает до `payload` как `null` (урок L95).
 */
import { Checkbox, Grid, NumberInput, Stack, Text, TextInput, Title } from '@mantine/core';

import type { Field, FormValues, GroupFields } from './form';

interface GroupProps {
  title: string;
  fields: GroupFields;
  onChange: (patch: Partial<GroupFields>) => void;
}

function Num({
  label,
  value,
  suffix,
  onChange,
}: {
  label: string;
  value: Field;
  suffix?: string;
  onChange: (value: Field) => void;
}) {
  return (
    <Grid.Col span={{ base: 12, sm: 6 }}>
      <NumberInput
        label={label}
        value={value}
        suffix={suffix}
        allowNegative={false}
        decimalScale={2}
        onChange={(next) => onChange(typeof next === 'number' ? next : '')}
      />
    </Grid.Col>
  );
}

function GroupFieldset({ title, fields, onChange }: GroupProps) {
  return (
    <Stack gap="xs">
      <Title order={5}>{title}</Title>
      <Grid>
        <Num
          label="Рост трафика от, %"
          value={fields.growthPctMin}
          onChange={(growthPctMin) => onChange({ growthPctMin })}
        />
        <Num
          label="Рост трафика до, % (пусто — без верхней границы)"
          value={fields.growthPctMax}
          onChange={(growthPctMax) => onChange({ growthPctMax })}
        />
        <Num
          label="Прирост не меньше, визитов"
          value={fields.growthAbsMin}
          onChange={(growthAbsMin) => onChange({ growthAbsMin })}
        />
        <Num
          label="Подтверждающих метрик нужно (0–2)"
          value={fields.supportingRequired}
          onChange={(supportingRequired) =>
            onChange({ supportingRequired: supportingRequired === '' ? 0 : supportingRequired })
          }
        />
        <Num
          label="Ссылающиеся домены от, %"
          value={fields.refdomainsPctMin}
          onChange={(refdomainsPctMin) => onChange({ refdomainsPctMin })}
        />
        <Num
          label="Ключи в топ-10 от, %"
          value={fields.kwTop10PctMin}
          onChange={(kwTop10PctMin) => onChange({ kwTop10PctMin })}
        />
        <Num
          label="Не раньше, месяцев после старта"
          value={fields.minMonths}
          onChange={(minMonths) => onChange({ minMonths })}
        />
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <Checkbox
            mt="xl"
            label="Сильный рост в процентах при малом приросте — сюда же"
            checked={fields.orHighPctLowAbs}
            onChange={(event) => onChange({ orHighPctLowAbs: event.currentTarget.checked })}
          />
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

interface Props {
  values: FormValues;
  onChange: (patch: Partial<FormValues>) => void;
}

export function ThresholdsForm({ values, onChange }: Props) {
  return (
    <Stack gap="md">
      <Grid>
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <TextInput
            label="Имя версии"
            placeholder="2026-09-II"
            value={values.version}
            onChange={(event) => onChange({ version: event.currentTarget.value })}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 6 }}>
          <TextInput
            label="Заметка: что изменили и зачем"
            value={values.note}
            onChange={(event) => onChange({ note: event.currentTarget.value })}
          />
        </Grid.Col>
      </Grid>

      <GroupFieldset
        title="Хороший"
        fields={values.good}
        onChange={(patch) => onChange({ good: { ...values.good, ...patch } })}
      />
      <GroupFieldset
        title="Средний"
        fields={values.medium}
        onChange={(patch) => onChange({ medium: { ...values.medium, ...patch } })}
      />

      <Title order={5}>Когда классифицировать вообще нельзя</Title>
      <Grid>
        <Num
          label="Не раньше, месяцев после старта"
          value={values.minMonthsAfterStart}
          onChange={(minMonthsAfterStart) => onChange({ minMonthsAfterStart })}
        />
        <Num
          label="Разрыв в рядах не больше, месяцев"
          value={values.maxGapMonths}
          onChange={(maxGapMonths) => onChange({ maxGapMonths })}
        />
        <Num
          label="Минимальный трафик точки Б, визитов"
          value={values.minTrafficPointB}
          onChange={(minTrafficPointB) => onChange({ minTrafficPointB })}
        />
        <Num
          label="Конец периода не ниже пика на, %"
          value={values.endVsPeakMinPct}
          onChange={(endVsPeakMinPct) => onChange({ endVsPeakMinPct })}
        />
      </Grid>

      <Text size="xs" c="dimmed">
        Окна точек А и Б, база отсчёта и веса счёта переносятся из версии-основы без изменений: они
        меняют смысл самих данных, а не границу группы.
      </Text>
    </Stack>
  );
}

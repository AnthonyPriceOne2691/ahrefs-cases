/**
 * Пороги: что утверждено сейчас.
 *
 * Самое опасное место сервиса — одна цифра перекладывает по группам всю базу и
 * решает, какие кейсы уйдут клиентам. Поэтому первое, на что экран отвечает, —
 * «по чему считается то, что я вижу на остальных экранах», и отвечает словами,
 * а не JSON'ом: пороги утверждают Head of Link Building и Owner.
 *
 * Список версий с предпросмотром последствий и правка приедут следующими
 * поставками; правка будет закрыта правом `edit_thresholds` и на сервере.
 */
import { Container, Stack, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { fetchRulesets } from '../api/thresholds';
import type { RulesetRow } from '../api/types';

import { CurrentVersion } from './thresholds/CurrentVersion';

/** Действующая версия — та, по которой посчитаны вердикты. Её нет только на
 *  сервисе, которому нечем классифицировать, и это говорится вслух. */
function active(rows: RulesetRow[] | undefined): RulesetRow | null {
  if (!rows || rows.length === 0) return null;
  return rows.find((row) => row.is_active) ?? rows[0] ?? null;
}

export function ThresholdsPage() {
  const rulesets = useQuery({ queryKey: ['rulesets'], queryFn: () => fetchRulesets() });

  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Пороги</Title>

        <CurrentVersion
          current={active(rulesets.data)}
          pending={rulesets.isPending}
          error={rulesets.isError ? rulesets.error : null}
          empty={rulesets.isSuccess && (rulesets.data?.length ?? 0) === 0}
        />
      </Stack>
    </Container>
  );
}

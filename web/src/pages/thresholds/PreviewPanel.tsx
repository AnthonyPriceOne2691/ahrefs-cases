/**
 * Предпросмотр: что будет, если считать по этой версии.
 *
 * Четыре состояния, а не два. «Сменит группу» и «получит вердикт впервые» —
 * разные события: второе не перекладывает проект, а достаёт его из небытия.
 * «Данных не хватает» — не разновидность «не изменится»: такой проект этой
 * версией считать нечем, и молчание о нём читается как «всё в порядке».
 */
import { Alert, Group, List, Stack, Text, Title } from '@mantine/core';

import type { PreviewChange, PreviewView } from '../../api/types';
import { groupWord } from '../groups';

function Changes({ title, items }: { title: string; items: PreviewChange[] }) {
  if (items.length === 0) return null;
  return (
    <Stack gap={4}>
      <Text size="sm" fw={600}>
        {title}: {items.length}
      </Text>
      <List size="sm" spacing={2} style={{ maxHeight: 220, overflowY: 'auto' }}>
        {items.map((item) => (
          <List.Item key={item.domain}>
            {item.domain}: {item.was === null ? 'нет вердикта' : groupWord(item.was)} →{' '}
            {groupWord(item.becomes)}
          </List.Item>
        ))}
      </List>
    </Stack>
  );
}

export function PreviewPanel({ preview }: { preview: PreviewView }) {
  const nothingMoves = preview.changes.length === 0 && preview.first_time.length === 0;
  // «Спокойно» говорится только тогда, когда посчитана вся база. Найдено
  // прогоном: зелёное «никто не сменит группу» стояло над жёлтым «данных не
  // хватает: 6» из 11 проектов — то есть успокаивало, не посчитав половину.
  const counted = preview.total - preview.missing_data.length;
  const allCounted = preview.missing_data.length === 0;

  return (
    <Stack gap="sm">
      <Group gap="xs">
        <Title order={5}>Версия {preview.version}</Title>
        <Text size="sm" c="dimmed">
          проектов в расчёте: {preview.total}
        </Text>
      </Group>

      {nothingMoves && (
        <Alert color={allCounted ? 'teal' : 'yellow'} variant="light">
          <Text size="sm">
            {allCounted
              ? `Никто не сменит группу: посчитаны все ${preview.total}, каждый остаётся в своей.`
              : `Из посчитанных никто не сменит группу — но посчитано ${counted} из ${preview.total}: остальным не хватает данных (ниже).`}
          </Text>
        </Alert>
      )}

      <Changes title="Сменят группу" items={preview.changes} />
      <Changes title="Получат вердикт впервые" items={preview.first_time} />

      <Text size="sm">Останутся в своей группе: {preview.unchanged}</Text>

      {preview.missing_data.length > 0 && (
        <Alert color="yellow" variant="light">
          <Text size="sm" fw={600}>
            Данных не хватает: {preview.missing_data.length}
          </Text>
          <Text size="xs">
            Этим проектам версия просит месяцы, которые не куплены. Они не «остались в своей группе»
            — их этой версией считать нечем: {preview.missing_data.join(', ')}
          </Text>
        </Alert>
      )}
    </Stack>
  );
}

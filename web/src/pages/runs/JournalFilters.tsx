/**
 * Отбор журнала: кто запускал и за какие дни.
 *
 * Журнал на стенде перевалил за пять сотен строк, и «свежие двадцать»
 * перестали отвечать на вопрос «что было в понедельник и кто это запускал»
 * (замечание владельца 15.09.2026).
 *
 * Поля — **родные**, а не всплывающие: `NativeSelect` и `input[type=date]`
 * рисуются браузером. Выпадающие списки и календари Mantine в jsdom
 * разворачиваются секундами, и оракул на них уходит в таймаут — грабли,
 * оплаченные в Ф6.
 *
 * Список авторов приходит с сервера, а не собирается по видимой странице:
 * иначе отбор «показать Петра» исчезал бы, стоило пролистнуть туда, где Петра
 * нет.
 */
import { Button, Group, NativeSelect, TextInput } from '@mantine/core';

import type { RunAuthor } from '../../api/types';

export interface JournalFilter {
  startedBy: number | null;
  since: string | null;
  until: string | null;
}

export const NO_FILTER: JournalFilter = { startedBy: null, since: null, until: null };

export function isFiltered(filter: JournalFilter): boolean {
  return filter.startedBy !== null || filter.since !== null || filter.until !== null;
}

interface Props {
  filter: JournalFilter;
  authors: RunAuthor[];
  onChange: (next: JournalFilter) => void;
}

export function JournalFilters({ filter, authors, onChange }: Props) {
  return (
    <Group align="flex-end" gap="sm" wrap="wrap">
      <NativeSelect
        label="Кто запустил"
        value={filter.startedBy === null ? '' : String(filter.startedBy)}
        onChange={(event) =>
          onChange({
            ...filter,
            startedBy: event.currentTarget.value ? Number(event.currentTarget.value) : null,
          })
        }
        data={[
          { value: '', label: 'все' },
          ...authors.map((author) => ({
            value: String(author.id),
            // Удалённая учётка остаётся в отборе: журнал живёт ради вопроса
            // «кто запускал», и вместе с уволившимся пропали бы его прогоны.
            label: author.deleted ? `${author.name} (удалён)` : author.name,
          })),
        ]}
        w={260}
      />
      <TextInput
        label="С даты"
        type="date"
        value={filter.since ?? ''}
        onChange={(event) => onChange({ ...filter, since: event.currentTarget.value || null })}
        w={170}
      />
      <TextInput
        label="По дату"
        type="date"
        value={filter.until ?? ''}
        onChange={(event) => onChange({ ...filter, until: event.currentTarget.value || null })}
        w={170}
      />
      {/* Кнопка показывается только когда есть что снимать: серая кнопка над
          пустым отбором — шум, который учатся не замечать. */}
      {isFiltered(filter) && (
        <Button variant="subtle" onClick={() => onChange(NO_FILTER)}>
          Снять отбор
        </Button>
      )}
    </Group>
  );
}

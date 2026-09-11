/**
 * Фильтры списка: поиск по домену и группа.
 *
 * Оба уходят **на сервер**: он отдаёт страницу, и фильтр по видимым строкам
 * сказал бы «хороших нет», когда они на второй.
 *
 * Группа выбирается чипами, а не выпадающим списком: значений пять вместе с
 * «любой», они взаимоисключающие и видны сразу — это один клик вместо двух и
 * никакого попапа на узком экране. (Побочно: попап Mantine в jsdom рендерится
 * секундами и не находится по подписи, то есть и проверить его дорого.)
 */
import { Chip, Group, Stack, Text, TextInput } from '@mantine/core';

const GROUPS = [
  { value: 'good', label: 'хорошие' },
  { value: 'medium', label: 'средние' },
  { value: 'poor', label: 'плохие' },
  // Четвёртая группа на месте: «данных не хватает» ведёт к докупке истории, а
  // не к отказу от кейса, и искать такие проекты нужно отдельно.
  { value: 'insufficient_data', label: 'данных не хватает' },
];

interface Props {
  group: string | null;
  query: string;
  onGroup: (value: string | null) => void;
  onQuery: (value: string) => void;
}

export function ProjectsFilters({ group, query, onGroup, onQuery }: Props) {
  return (
    <Stack gap="sm">
      <TextInput
        label="Поиск по домену"
        placeholder="example.com"
        value={query}
        onChange={(event) => onQuery(event.currentTarget.value)}
      />
      <Stack gap={4}>
        <Text size="sm" fw={500}>
          Группа
        </Text>
        <Group gap="xs" wrap="wrap">
          <Chip checked={group === null} onChange={() => onGroup(null)} variant="light">
            любая
          </Chip>
          {GROUPS.map((item) => (
            <Chip
              key={item.value}
              checked={group === item.value}
              onChange={() => onGroup(group === item.value ? null : item.value)}
              variant="light"
            >
              {item.label}
            </Chip>
          ))}
        </Group>
      </Stack>
    </Stack>
  );
}

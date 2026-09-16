/**
 * Шапка карточки: чей это проект и что с ним решили.
 *
 * Версия порогов стоит рядом с группой не для полноты: вердикты разных версий
 * живут в базе одновременно, и число без версии ничего не значит — по другой
 * версии тот же проект может оказаться в другой группе.
 */
import { Anchor, Badge, Group, Stack, Text, Title } from '@mantine/core';
import { Link } from 'react-router-dom';

import type { ProjectCard } from '../../api/types';
import { GroupBadge } from '../projects/GroupBadge';
import { months } from '../format';

export function CardHeader({ card }: { card: ProjectCard }) {
  const { project, verdict } = card;
  return (
    <Stack gap="xs">
      <Anchor component={Link} to="/projects" size="sm">
        ← к списку проектов
      </Anchor>
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Stack gap={2}>
          <Title order={2}>{project.domain}</Title>
          <Text size="sm" c="dimmed">
            {project.niche} · {project.geo} · {months(project.period_start, project.period_end)}
          </Text>
        </Stack>
        <Group gap="xs" align="center">
          <GroupBadge group={project.group} />
          {/* Счёта в шапке нет намеренно (решение владельца 16.09.2026): это
              взвешенная сумма процентов и визитов без единиц измерения —
              «−19 745» у проекта, где трафик упал на 100 % и на 65 683
              визита. Число работает только там, где сравнивают соседей, то
              есть в сортировке списка; в карточке одного проекта сравнивать
              не с чем, и оно читалось как оценка, которой не является. */}
          {verdict && (
            <Badge variant="light" color="gray" data-ruleset={verdict.ruleset_version}>
              пороги {verdict.ruleset_version}
            </Badge>
          )}
          {project.publishable ? null : (
            <Badge variant="light" color="gray">
              публиковать без названия
            </Badge>
          )}
        </Group>
      </Group>
    </Stack>
  );
}

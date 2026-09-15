/**
 * Оболочка: шапка, меню по правам, полотно.
 *
 * Раскладка перенесена из CRM линкбилдинга (там это отлаженное поведение),
 * оформление — из визуального языка local-web-agent: стекло поверх насыщенного
 * полотна. Tailwind при этом не тащим — здесь Mantine, и две системы стилей
 * пришлось бы красить дважды.
 */
import { AppShell, Badge, Burger, Button, Group, NavLink, Stack, Text, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';

import { NAV_SECTIONS, visibleSections } from './nav';
import { ThemeToggle } from './ThemeToggle';

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [opened, { toggle }] = useDisclosure();
  const location = useLocation();
  const sections = visibleSections(user?.rights ?? []);
  const visited = useVisited(location.pathname + location.search);

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="lg"
    >
      <AppShell.Header>
        {/* `wrap="nowrap"` — не косметика: высота шапки задана жёстко (56 px),
            и перенос второй строки на узком экране наезжал на содержимое.
            Почта уходит первой: из четырёх элементов она самая длинная и
            единственная, которую человек про себя и так знает. Группа и выход
            остаются — одно отвечает «под кем я вижу этот экран», второе нужно
            на чужом ноутбуке. */}
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={3} style={{ whiteSpace: 'nowrap' }}>
              Ahrefs Cases
            </Title>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Text size="sm" c="dimmed" visibleFrom="sm" data-shell="email">
              {user?.email}
            </Text>
            <Badge variant="light">{user?.group}</Badge>
            <Button variant="subtle" size="xs" onClick={logout}>
              Выйти
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        {/* Разделы забирают всю высоту, переключатель темы остаётся под ними:
            он не раздел, и в одном ряду с ними читался бы восьмым пунктом
            меню. Колонка у Mantine — флекс-столбец, поэтому «прижат к низу»
            делается ростом списка, а не отступом на глаз. */}
        <Stack gap={4} style={{ flexGrow: 1 }}>
          {sections.map((section) => (
            <NavLink
              key={section.path}
              component={Link}
              /* Ведёт туда, где человек в этом разделе был: фильтры и страница
                 живут в адресе, и голая ссылка сбрасывала бы их при каждом
                 переходе туда-обратно. */
              to={visited[section.path] ?? section.path}
              label={section.label}
              active={location.pathname.startsWith(section.path)}
            />
          ))}
        </Stack>
        <Group justify="flex-start" pt="xs" className="navFooter">
          <ThemeToggle />
        </Group>
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}

/**
 * Где человек был в каждом разделе — чтобы меню вернуло его туда же.
 *
 * Состояние экранов живёт в адресе (`app/screenState.ts`), а пункт меню ведёт
 * на голый путь: без памяти переход «Проекты → Кейсы → Проекты» сбрасывал бы
 * фильтры и страницу, хотя человек никуда из раздела не уходил.
 *
 * Помнится только текущая вкладка и только пока она открыта: это удобство, а
 * не данные. Пережить F5 адресу помогает сам адрес.
 */
function useVisited(current: string): Record<string, string> {
  const [visited, setVisited] = useState<Record<string, string>>({});

  useEffect(() => {
    const section = NAV_SECTIONS.find((item) => current.startsWith(item.path));
    if (!section || visited[section.path] === current) return;
    setVisited((was) => ({ ...was, [section.path]: current }));
  }, [current, visited]);

  return visited;
}

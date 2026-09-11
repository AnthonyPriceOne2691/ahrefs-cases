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
import { Link, useLocation } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';

import { visibleSections } from './nav';

export function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [opened, { toggle }] = useDisclosure();
  const location = useLocation();
  const sections = visibleSections(user?.rights ?? []);

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="lg"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={3}>Ahrefs Cases</Title>
          </Group>
          <Group gap="sm">
            <Text size="sm" c="dimmed">
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
        <Stack gap={4}>
          {sections.map((section) => (
            <NavLink
              key={section.path}
              component={Link}
              to={section.path}
              label={section.label}
              active={location.pathname.startsWith(section.path)}
            />
          ))}
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}

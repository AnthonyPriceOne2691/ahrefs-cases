/**
 * Маршруты. Пока экранов нет — заглушки с честным текстом, а не пустые страницы.
 *
 * Заглушка называет, какой поставкой придёт экран: пустая страница без объяснения
 * читается как поломка, и первым делом её идут чинить.
 */
import { Alert, Container, Stack, Text, Title } from '@mantine/core';
import { Navigate, Route, Routes } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';

import { NAV_SECTIONS } from './nav';

function Placeholder({ title }: { title: string }) {
  return (
    <Container size="lg">
      <Stack gap="sm">
        <Title order={2}>{title}</Title>
        <Alert variant="light">
          <Text size="sm">
            Экран приезжает следующими поставками Ф6. Данные для него уже отдаёт API — это вопрос
            вёрстки, а не логики.
          </Text>
        </Alert>
      </Stack>
    </Container>
  );
}

export function AppRoutes() {
  const { can } = useAuth();
  const allowed = NAV_SECTIONS.filter((section) => section.right === null || can(section.right));
  const home = allowed[0]?.path ?? '/projects';

  return (
    <Routes>
      {allowed.map((section) => (
        <Route
          key={section.path}
          path={section.path}
          element={<Placeholder title={section.label} />}
        />
      ))}
      {/* Раздел без права не просто спрятан в меню: адрес, введённый руками,
          ведёт на разрешённый экран. Это удобство, а не защита — проверки
          стоят на сервере и остаются. */}
      <Route path="*" element={<Navigate to={home} replace />} />
    </Routes>
  );
}

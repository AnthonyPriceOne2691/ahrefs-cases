/**
 * Кейсы: библиотека собранного и выдача пачки.
 *
 * Единственный экран, с которого что-то уходит клиенту, — поэтому он отвечает
 * не только «что собрано», но и «что из этого можно публиковать под именем».
 *
 * Файлы скачиваются запросом с токеном, а не ссылкой: авторизация у нас
 * заголовком, и прямая ссылка вернула бы `401` вместо кейса.
 */
import { Container, Paper, Stack, Title } from '@mantine/core';

import { CaseLibrary } from './cases/CaseLibrary';
import { PackSection } from './cases/PackSection';

export function CasesPage() {
  return (
    <Container size="xl">
      <Stack gap="lg">
        <Title order={2}>Кейсы</Title>

        <Paper className="glass" p="lg">
          <PackSection />
        </Paper>

        <Paper className="glass" p="lg">
          <CaseLibrary />
        </Paper>
      </Stack>
    </Container>
  );
}

/**
 * Два способа дать список: файл и ссылка на Google Sheet.
 *
 * Оба названы в ТЗ, и оба нужны: отдел присылает то файл, то ссылку, а
 * спрашивать у него формат значит спрашивать дважды.
 */
import { Alert, Button, FileInput, Group, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';

interface Props {
  busy: boolean;
  error: string | null;
  onSubmit: (source: File | string) => void;
}

export function SourceForm({ busy, error, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [link, setLink] = useState('');

  return (
    <Stack gap="md">
      <Text size="sm">
        Список проектов — XLSX или CSV, либо ссылка на опубликованную Google Sheet. Нужны все десять
        колонок; строки без них попадут в отчёт с причиной, а остальные примутся.
      </Text>

      <Group align="flex-end" wrap="wrap">
        <FileInput
          label="Файл со списком"
          placeholder="выбрать файл"
          accept=".xlsx,.xlsm,.csv"
          value={file}
          onChange={setFile}
          flex="1 1 16rem"
        />
        <Button onClick={() => file && onSubmit(file)} disabled={!file || busy} loading={busy}>
          Загрузить файл
        </Button>
      </Group>

      <Group align="flex-end" wrap="wrap">
        <TextInput
          label="Ссылка на Google Sheet"
          placeholder="https://docs.google.com/spreadsheets/…"
          value={link}
          onChange={(event) => setLink(event.currentTarget.value)}
          flex="1 1 16rem"
        />
        <Button
          variant="light"
          onClick={() => link.trim() && onSubmit(link.trim())}
          disabled={!link.trim() || busy}
        >
          Загрузить по ссылке
        </Button>
      </Group>

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}
    </Stack>
  );
}

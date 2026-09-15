/**
 * Два способа дать список: файл и ссылка на Google Sheet.
 *
 * Оба названы в ТЗ, и оба нужны: отдел присылает то файл, то ссылку, а
 * спрашивать у него формат значит спрашивать дважды.
 */
import { Alert, Button, FileButton, Group, Stack, Text, TextInput } from '@mantine/core';
import { useState } from 'react';

import { SheetHelp } from './SheetHelp';

const BUTTON_WIDTH = 210;
/** Поля укорочены: список путей к файлу и ссылка на таблицу — короткие строки,
 *  а поле во всю ширину обещает длинный ввод и уводит кнопку к краю экрана. */
const FIELD_WIDTH = 420;

interface Props {
  busy: boolean;
  error: string | null;
  onSubmit: (source: File | string) => void;
}

export function SourceForm({ busy, error, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [link, setLink] = useState('');

  return (
    <Stack gap="md">
      <Text size="sm">
        Список проектов — XLSX или CSV, либо ссылка на опубликованную Google Sheet. Нужны все десять
        колонок; строки без них попадут в отчёт с причиной, а остальные примутся.
      </Text>

      {/*
        Кнопка сама открывает выбор файла и сама его отправляет — одно движение
        вместо двух. Прежде выбор делало поле, а кнопка стояла недоступной, пока
        файл не выбран: она выглядела сломанной и, по словам владельца, «по сути
        ничего не делает» (15.09.2026). Поле рядом теперь только показывает имя
        выбранного — вводить в него нечего, поэтому оно `readOnly`.
      */}
      <Group align="flex-end" wrap="wrap">
        <TextInput
          label="Файл со списком"
          placeholder="файл не выбран"
          value={name}
          readOnly
          w={FIELD_WIDTH}
          data-chosen-file={name || undefined}
        />
        {/* Ширина кнопок задана одинаковой нарочно: иначе её задаёт длина
            надписи, и поля над ними получаются разной длины — «Загрузить по
            ссылке» на два символа длиннее «Загрузить файл». */}
        <FileButton
          accept=".xlsx,.xlsm,.csv"
          onChange={(chosen) => {
            if (!chosen) return;
            setName(chosen.name);
            onSubmit(chosen);
          }}
        >
          {(props) => (
            <Button {...props} disabled={busy} loading={busy} w={BUTTON_WIDTH}>
              Загрузить файл
            </Button>
          )}
        </FileButton>
      </Group>

      <Group align="flex-end" wrap="wrap">
        {/*
          Подпись и знак справки — соседи, а НЕ содержимое `<label>`: кнопка
          внутри подписи склеивает своё имя с именем поля («Ссылка на Google
          Sheet какой должна быть таблица») и наводит фокус на поле по нажатию
          на значок. Поэтому подпись рисуется сама, а поле получает своё имя
          через `aria-label`.
        */}
        <Stack gap={4} w={FIELD_WIDTH}>
          <Group gap={6} align="center">
            <Text size="sm" fw={500}>
              Ссылка на Google Sheet
            </Text>
            <SheetHelp />
          </Group>
          <TextInput
            aria-label="Ссылка на Google Sheet"
            placeholder="https://docs.google.com/spreadsheets/…"
            value={link}
            onChange={(event) => setLink(event.currentTarget.value)}
          />
        </Stack>
        <Button
          variant="light"
          onClick={() => link.trim() && onSubmit(link.trim())}
          disabled={!link.trim() || busy}
          w={BUTTON_WIDTH}
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

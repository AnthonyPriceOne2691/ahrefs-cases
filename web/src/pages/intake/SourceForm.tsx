/**
 * Два способа дать список: файл и ссылка на Google Sheet.
 *
 * Оба названы в ТЗ, и оба нужны: отдел присылает то файл, то ссылку, а
 * спрашивать у него формат значит спрашивать дважды.
 *
 * Отказ сервера стоит **у того поля, которым давали список**. Отказ целиком —
 * «файл не подходит», «таблица недоступна» — чинится в источнике, и плашка
 * посреди формы не говорит, в каком из двух.
 */
import { Alert, Button, FileButton, Group, Stack, Text, TextInput } from '@mantine/core';
import { useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { FILE_ACCEPT, FileHelp, MAX_MEGABYTES, SheetHelp } from './ListHelp';

const BUTTON_WIDTH = 210;
/** Поля укорочены: список путей к файлу и ссылка на таблицу — короткие строки,
 *  а поле во всю ширину обещает длинный ввод и уводит кнопку к краю экрана. */
const FIELD_WIDTH = 420;
/** Плашка отказа — шириной строки «поле и кнопка», а не всей карточки. */
const ROW_WIDTH = FIELD_WIDTH + BUTTON_WIDTH + 16;
const MAX_BYTES = MAX_MEGABYTES * 1024 * 1024;

type Source = 'file' | 'link';

interface Props {
  busy: boolean;
  error: string | null;
  onSubmit: (source: File | string) => void;
}

/**
 * Подпись поля и знак справки — соседи, а НЕ содержимое `<label>`: кнопка
 * внутри подписи склеивает своё имя с именем поля («Ссылка на Google Sheet
 * какой должна быть таблица») и наводит фокус на поле по нажатию на значок
 * (урок L192). Поэтому подпись рисуется сама, а поле получает имя через
 * `aria-label`.
 */
function Labelled({
  label,
  help,
  children,
}: {
  label: string;
  help: ReactNode;
  children: ReactNode;
}) {
  return (
    <Stack gap={4} w={FIELD_WIDTH}>
      <Group gap={6} align="center">
        <Text size="sm" fw={500}>
          {label}
        </Text>
        {help}
      </Group>
      {children}
    </Stack>
  );
}

function Refusal({ text }: { text: string }) {
  return (
    <Alert color="red" variant="light" maw={ROW_WIDTH}>
      <Text size="sm">{text}</Text>
    </Alert>
  );
}

/**
 * Кнопка сама открывает выбор файла и сама его отправляет — одно движение
 * вместо двух. Прежде выбор делало поле, а кнопка стояла недоступной, пока
 * файл не выбран: она выглядела сломанной и, по словам владельца, «по сути
 * ничего не делает» (15.09.2026). Поле рядом только показывает имя
 * выбранного — вводить в него нечего, поэтому оно `readOnly`.
 */
function FileField({ busy, onChosen }: { busy: boolean; onChosen: (file: File) => void }) {
  const [name, setName] = useState('');
  const resetChoice = useRef<() => void>(null);

  return (
    <Group align="flex-end" wrap="wrap">
      <Labelled label="Файл со списком" help={<FileHelp />}>
        <TextInput
          aria-label="Файл со списком"
          placeholder="файл не выбран"
          value={name}
          readOnly
          data-chosen-file={name || undefined}
        />
      </Labelled>
      {/* Ширина кнопок задана одинаковой нарочно: иначе её задаёт длина
          надписи, и поля над ними получаются разной длины — «Загрузить по
          ссылке» на два символа длиннее «Загрузить файл». */}
      <FileButton
        accept={FILE_ACCEPT}
        resetRef={resetChoice}
        onChange={(chosen) => {
          if (!chosen) return;
          setName(chosen.name);
          onChosen(chosen);
          // Поле выбора пустеет сразу: браузер не шлёт `change`, если выбран
          // тот же файл, что уже стоит в поле, — и список, поправленный после
          // отказа, иначе не ушёл бы вовсе. Файл к этому мгновению уже взят.
          resetChoice.current?.();
        }}
      >
        {(props) => (
          <Button {...props} disabled={busy} loading={busy} w={BUTTON_WIDTH}>
            Загрузить файл
          </Button>
        )}
      </FileButton>
    </Group>
  );
}

export function SourceForm({ busy, error, onSubmit }: Props) {
  const [link, setLink] = useState('');
  const [asked, setAsked] = useState<Source | null>(null);
  const [tooBig, setTooBig] = useState<string | null>(null);
  const refusal = tooBig ?? error;

  const submit = (source: Source, value: File | string) => {
    setAsked(source);
    setTooBig(null);
    onSubmit(value);
  };

  /**
   * Файл больше предела не отправляется. Сервер отказал бы и сам (`413` с
   * пределом в тексте), но через прокси этот ответ до человека не доходит:
   * сервер закрывает соединение, не дочитав тело, прокси ловит `EPIPE` и
   * отвечает своей ошибкой — на проверке это было «сервер ответил 500».
   * Предел — из тех же данных, что подсказка; с сервером их сверяет тест.
   */
  const choose = (chosen: File) => {
    if (chosen.size <= MAX_BYTES) return submit('file', chosen);
    setAsked('file');
    setTooBig(
      `Файл «${chosen.name}» больше ${MAX_MEGABYTES} МБ: ожидается список проектов, а не ` +
        'выгрузка целиком. Файл не отправлен.',
    );
  };

  return (
    <Stack gap="md">
      <Text size="sm">
        Список проектов — XLSX или CSV, либо ссылка на опубликованную Google Sheet. Нужны все десять
        колонок: без них список не принимается целиком, а строки с браком попадут в отчёт с
        причиной, остальные примутся. Какие колонки — под знаком «?».
      </Text>

      <FileField busy={busy} onChosen={choose} />
      {refusal && asked === 'file' && <Refusal text={refusal} />}

      <Group align="flex-end" wrap="wrap">
        <Labelled label="Ссылка на Google Sheet" help={<SheetHelp />}>
          <TextInput
            aria-label="Ссылка на Google Sheet"
            placeholder="https://docs.google.com/spreadsheets/…"
            value={link}
            onChange={(event) => setLink(event.currentTarget.value)}
          />
        </Labelled>
        <Button
          variant="light"
          onClick={() => link.trim() && submit('link', link.trim())}
          disabled={!link.trim() || busy}
          w={BUTTON_WIDTH}
        >
          Загрузить по ссылке
        </Button>
      </Group>
      {refusal && asked === 'link' && <Refusal text={refusal} />}
    </Stack>
  );
}

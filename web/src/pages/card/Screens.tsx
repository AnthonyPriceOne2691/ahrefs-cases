/**
 * Скрины для брифа на карточке: посмотреть, загрузить, удалить.
 *
 * Скрин отчёта Ahrefs или экрана видимости бренда в ИИ специалист снимает по
 * ссылке из PDF-брифа и загружает сюда; в PDF он встаёт разделом «Скрины».
 * Загрузка и удаление — под правом `edit_briefs`, как бриф; смотрят все, кто
 * читает проект.
 *
 * Виды словами и пределы — с сервера (`/api/screenshot-rules`): экран ужимает
 * большой снимок и отказывает по тем же числам, что сервер, а не по копии.
 * Поля — родные (`NativeSelect`), подтверждение удаления — на месте, а не
 * попапом (урок L76).
 */
import {
  Alert,
  Button,
  FileButton,
  Group,
  Image,
  NativeSelect,
  Paper,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import {
  deleteScreenshot,
  fetchScreenshotImage,
  fetchScreenshotRules,
  fetchScreenshots,
  uploadScreenshot,
} from '../../api/screenshots';
import type { ScreenshotRules, ScreenshotView } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { ConfirmDelete } from '../../components/ConfirmDelete';
import { failureText } from '../cases/failure';
import { megabytes } from '../format';

import { fitForUpload } from './shrink';

const ACCEPT = 'image/png,image/jpeg,image/webp';

export function Screens({ projectId }: { projectId: number }) {
  const { can } = useAuth();
  const rules = useQuery({
    queryKey: ['screenshot-rules'],
    queryFn: fetchScreenshotRules,
    staleTime: Infinity,
  });
  const shots = useQuery({
    queryKey: ['screenshots', projectId],
    queryFn: () => fetchScreenshots(projectId),
  });
  const failed = rules.error ?? shots.error;
  const editor = can('edit_briefs');

  return (
    <Paper className="glass" p="lg">
      <Stack gap="sm">
        <Title order={3}>Скрины для брифа</Title>
        <Text size="sm" c="dimmed">
          Отчёты Ahrefs и экраны видимости бренда в ИИ встают в PDF-бриф разделом «Скрины». Ссылки
          на отчёты Ahrefs — в PDF, под пунктами брифа.
        </Text>
        {failed && (
          <Text size="sm" c="dimmed">
            Скрины не загрузились: {failureText(failed, failed.message)}
          </Text>
        )}
        {rules.data && shots.data && (
          <>
            <Gallery projectId={projectId} rules={rules.data} shots={shots.data} editor={editor} />
            {editor && (
              <Upload projectId={projectId} rules={rules.data} count={shots.data.length} />
            )}
          </>
        )}
      </Stack>
    </Paper>
  );
}

interface GalleryProps {
  projectId: number;
  rules: ScreenshotRules;
  shots: ScreenshotView[];
  editor: boolean;
}

function Gallery({ projectId, rules, shots, editor }: GalleryProps) {
  if (shots.length === 0) return <Text size="sm">Скринов пока нет.</Text>;
  const labels = new Map(rules.kinds.map((kind) => [kind.key, kind.label]));
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
      {shots.map((shot) => {
        const kind = labels.get(shot.kind) ?? shot.kind;
        const title = shot.caption ? `${kind} · ${shot.caption}` : kind;
        return (
          <Stack gap={4} key={shot.id} data-screenshot={shot.id}>
            <Thumb id={shot.id} title={title} />
            <Text size="sm">{title}</Text>
            {editor && <Remove projectId={projectId} id={shot.id} title={title} />}
          </Stack>
        );
      })}
    </SimpleGrid>
  );
}

/** Миниатюра — `data:`-адрес из запроса с токеном: картинка по `id` не меняется. */
function Thumb({ id, title }: { id: number; title: string }) {
  const image = useQuery({
    queryKey: ['screenshot-image', id],
    queryFn: () => fetchScreenshotImage(id),
    staleTime: Infinity,
  });
  if (image.data) return <Image src={image.data} alt={title} radius="sm" />;
  return (
    <Text size="xs" c="dimmed">
      {image.isError ? 'картинка не открылась' : 'картинка загружается…'}
    </Text>
  );
}

function Remove({ projectId, id, title }: { projectId: number; id: number; title: string }) {
  const queryClient = useQueryClient();
  const [asked, setAsked] = useState(false);
  const drop = useMutation({
    mutationFn: () => deleteScreenshot(id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['screenshot-image', id] });
      void queryClient.invalidateQueries({ queryKey: ['screenshots', projectId] });
    },
  });
  if (!asked) {
    // В группе, а не прямо в столбце: столбец растянул бы кнопку на ширину миниатюры.
    return (
      <Group>
        <Button
          variant="subtle"
          color="red"
          size="compact-sm"
          aria-label={`Удалить скрин «${title}»`}
          onClick={() => setAsked(true)}
        >
          Удалить
        </Button>
      </Group>
    );
  }
  return (
    <Stack gap={0}>
      <Text size="sm">Удалить скрин из брифа? Файл сотрётся.</Text>
      <ConfirmDelete
        busy={drop.isPending}
        onConfirm={() => drop.mutate()}
        onCancel={() => setAsked(false)}
      />
      {drop.isError && (
        <Text size="sm" c="red">
          {failureText(drop.error, 'скрин не удалился')}
        </Text>
      )}
    </Stack>
  );
}

function Upload({
  projectId,
  rules,
  count,
}: {
  projectId: number;
  rules: ScreenshotRules;
  count: number;
}) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState(rules.kinds[0]?.key ?? '');
  const [caption, setCaption] = useState('');
  const resetChoice = useRef<() => void>(null);
  const limits = { maxBytes: rules.max_bytes, maxSide: rules.max_side };
  const send = useMutation({
    mutationFn: async (file: File) =>
      uploadScreenshot(projectId, await fitForUpload(file, limits), kind, caption.trim()),
    onSuccess: () => {
      setCaption('');
      void queryClient.invalidateQueries({ queryKey: ['screenshots', projectId] });
    },
  });
  const full = count >= rules.max_count;

  return (
    <Stack gap="xs">
      <Group align="flex-end" wrap="wrap">
        <NativeSelect
          label="Вид скрина"
          data={rules.kinds.map((item) => ({ value: item.key, label: item.label }))}
          value={kind}
          onChange={(event) => setKind(event.currentTarget.value)}
        />
        <TextInput
          label="Подпись"
          placeholder="Обзор: органический трафик · Германия (DE)"
          maxLength={300}
          value={caption}
          onChange={(event) => setCaption(event.currentTarget.value)}
          w={360}
        />
        <FileButton
          accept={ACCEPT}
          resetRef={resetChoice}
          onChange={(file) => {
            if (!file) return;
            send.mutate(file);
            // Тот же файл после отказа выбирается снова: без сброса браузер не шлёт `change`.
            resetChoice.current?.();
          }}
        >
          {(props) => (
            <Button {...props} loading={send.isPending} disabled={full}>
              Загрузить скрин
            </Button>
          )}
        </FileButton>
      </Group>
      <Text size="xs" c="dimmed">
        PNG, JPEG или WebP до {megabytes(rules.max_bytes)} МБ; снимок крупнее ужмётся перед
        отправкой.
      </Text>
      {full && (
        <Text size="sm">
          У проекта уже {rules.max_count} скринов — удалите лишние, чтобы загрузить новый.
        </Text>
      )}
      {send.isError && (
        <Alert color="red" variant="light" p="xs">
          <Text size="sm">{failureText(send.error, send.error.message)}</Text>
        </Alert>
      )}
    </Stack>
  );
}

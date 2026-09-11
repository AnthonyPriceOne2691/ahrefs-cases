/**
 * Что делать с сохранённой версией: посмотреть последствия и применить.
 *
 * Применение — **второе нажатие той же кнопки**. Не модальное окно (попапы
 * Mantine в jsdom стоят секунд, урок L76) и не одно нажатие: активация меняет
 * группы для всех, кто откроет сервис после неё.
 */
import { Alert, Button, Code, Group, Stack, Text } from '@mantine/core';

import type { PreviewView, RecalcView } from '../../api/types';

import { PreviewPanel } from './PreviewPanel';

interface Props {
  version: string;
  active: boolean;
  preview: PreviewView | null;
  recalc: RecalcView | null;
  confirming: boolean;
  applying: boolean;
  recalculating: boolean;
  onApply: () => void;
  onRecalc: () => void;
}

export function ApplyPanel({
  version,
  active,
  preview,
  recalc,
  confirming,
  applying,
  recalculating,
  onApply,
  onRecalc,
}: Props) {
  return (
    <Stack gap="sm">
      {/* Плашка обязана знать, что версию уже применили: найдено прогоном —
          после активации она продолжала говорить «пока не действует». */}
      <Alert color="teal" variant="light">
        <Text size="sm">
          {active ? (
            <>
              Версия {version} <strong>действует</strong>: следующая классификация пойдёт по ней.
            </>
          ) : (
            <>
              Версия {version} сохранена и пока <strong>не действует</strong>: вердикты считаются по
              прежней.
            </>
          )}
        </Text>
      </Alert>

      {preview && <PreviewPanel preview={preview} />}

      <Group gap="sm">
        {!active && (
          <Button color={confirming ? 'red' : 'blue'} loading={applying} onClick={onApply}>
            {confirming ? 'Точно применить? Нажмите ещё раз' : 'Применить версию'}
          </Button>
        )}
        {active && (
          <Button variant="light" loading={recalculating} onClick={onRecalc}>
            Пересчитать вердикты
          </Button>
        )}
      </Group>

      {active && !recalc && (
        <Text size="xs" c="dimmed">
          Версия действует. Пока вердикты остались прежними: пересчёт — отдельный шаг, он
          переписывает группы проектов и бесплатен (Ahrefs не трогается).
        </Text>
      )}

      {recalc && <Code block>{recalc.lines.join('\n')}</Code>}
    </Stack>
  );
}

/**
 * Служебное: ступени воронки по всей базе — свёрнутым блоком под журналом.
 *
 * Обычный путь один: загрузить список и нажать «Запустить» цикла по файлу. Две
 * кнопки по всей базе стояли рядом с ним на виду и сбивали с толку: «Смета и
 * запуск» делала только шаг 1, и 25.09 и 12.10.2026 её нажимали вместо цикла —
 * кейсы не появлялись (Z61). Решение владельца 13.10.2026: шаг 1 по базе с экрана
 * снять, «Дособрать кандидатов» убрать с видного места.
 *
 * Сама кнопка нужна, но редко, и блок говорит когда: после смены порогов среди
 * старых проектов появляются новые кандидаты, и докупить им данные без повторной
 * загрузки файлов можно только ею; и если цикл встал посередине. Раскрытие
 * переживает F5 тем же признаком в адресе, что окно сметы (L182).
 */
import { Button, Paper, Stack, Text } from '@mantine/core';

import type { RunRow } from '../../api/types';
import { useStickyFlag } from '../../app/stickyFlag';

import { Stage2Launcher } from './Stage2Launcher';

interface Props {
  run: RunRow | null;
  onStarted: (runId: number) => void;
}

export function ServiceRuns({ run, onStarted }: Props) {
  const [opened, setOpened] = useStickyFlag('служебное');

  return (
    <Paper className="glass" p="lg" data-service-runs>
      <Stack gap="sm" align="flex-start">
        <Button variant="subtle" aria-expanded={opened} onClick={() => setOpened(!opened)}>
          Служебное: дособрать данные по всей базе
        </Button>
        {opened && (
          <>
            <Text size="sm">
              Шаг 2 и данные под кейс — для всех кандидатов базы, у кого их ещё нет. Нужно редко:
              после смены порогов, когда среди старых проектов появились новые кандидаты, или если
              цикл по файлу встал посередине. Обычная работа — загрузить список и нажать «Запустить»
              под отчётом о приёме.
            </Text>
            <Stage2Launcher run={run} onStarted={onStarted} />
          </>
        )}
      </Stack>
    </Paper>
  );
}

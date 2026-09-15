/**
 * Смета прогона в окне.
 *
 * Почему окном, а не плашкой на странице: смета — это решение («запускать ли»),
 * а не сводка, которую читают между делом. Плашка стояла третьей на экране и
 * пролистывалась вместе с ним.
 *
 * **Окно не закрывается само** — ни от F5, ни от ухода в соседний раздел: смету
 * смотрят не одну секунду, и закрывать её за человека, пока он ходил сверяться
 * с проектами, значит заставить открывать заново.
 *
 * **Числа при этом не запоминаются, а переспрашиваются.** Решение владельца
 * 15.09.2026, и оно про цену ошибки: между F5 мог пройти чужой прогон и съесть
 * квоту, а по этим числам нажимают «Запустить прогон». Сохранённая смета
 * показала бы вчерашний остаток — и кнопка под ней выглядела бы разрешённой.
 */
import { Alert, Button, Modal, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';

import { ApiError } from '../../api/client';
import { fetchEstimate } from '../../api/intake';
import type { RunRow } from '../../api/types';
import { EstimatePanel } from '../intake/EstimatePanel';

export const ESTIMATE_KEY = ['runs', 'estimate'];

interface Props {
  opened: boolean;
  onClose: () => void;
  run: RunRow | null;
  starting: boolean;
  startError: string | null;
  onStart: () => void;
}

export function EstimateWindow({ opened, onClose, run, starting, startError, onStart }: Props) {
  const estimate = useQuery({
    queryKey: ESTIMATE_KEY,
    queryFn: fetchEstimate,
    // Считается, только когда окно открыто: смета проходит по всем проектам
    // базы и спрашивает у Ahrefs остаток — делать это на каждой загрузке
    // экрана, который открыли ради журнала, незачем.
    enabled: opened,
    // Открыли снова — считаем снова. Устаревшая смета опаснее ожидания.
    staleTime: 0,
  });

  return (
    <Modal opened={opened} onClose={onClose} title="Смета прогона" size="lg" centered>
      <Stack gap="md">
        {estimate.isPending && <Text size="sm">Считаем смету…</Text>}
        {estimate.isError && (
          <Alert color="red" variant="light">
            <Text size="sm">
              {estimate.error instanceof ApiError ? estimate.error.message : 'смета не посчитана'}
            </Text>
          </Alert>
        )}
        {estimate.data && (
          <EstimatePanel
            estimate={estimate.data}
            run={run}
            starting={starting}
            startError={startError}
            onStart={onStart}
          />
        )}
        <Button variant="subtle" onClick={onClose}>
          Закрыть
        </Button>
      </Stack>
    </Modal>
  );
}

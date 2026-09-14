/**
 * Библиотека собранных кейсов: что есть и что из этого можно забрать.
 *
 * Скачивание живёт здесь, а не в таблице: таблица показывает строки, а запрос
 * с токеном и сохранение файла — работа экрана.
 */
import { Alert, Group, Stack, Switch, Text } from '@mantine/core';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { downloadCase, fetchCases } from '../../api/cases';
import type { CaseRow } from '../../api/types';
import { usePagedScreen } from '../../app/screenState';
import { Pager } from '../../components/Pager';

import { CasesTable } from './CasesTable';
import { failureText } from './failure';
import { saveFile } from './save';

const PAGE_SIZE = 20;
/** Столько строк видно без прокрутки. Библиотека росла до полусотни и
 *  обрывалась молча: сервер отдавал первые пятьдесят, а человек видел в них
 *  всю выдачу. */

/** Листалка показывается, только когда есть что листать: на одной неполной
 *  странице две серые кнопки — шум, который человек учится не замечать. */
function LibraryPager({
  rows,
  page,
  onChange,
}: {
  rows: CaseRow[] | undefined;
  page: number;
  onChange: (value: number) => void;
}) {
  const full = rows?.length === PAGE_SIZE;
  if (!rows || (page === 0 && !full)) {
    return null;
  }
  return <Pager page={page} full={full} onChange={onChange} />;
}

export function CaseLibrary() {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Страница и тумблер версий — в адресе: F5 и переход в соседний раздел не
  // должны возвращать человека в начало списка.
  const { screen, page, setPage } = usePagedScreen();
  const [allVersions, setAllVersions] = useState(screen.flag('версии'));

  const cases = useQuery({
    queryKey: ['cases', 'library', allVersions, page],
    queryFn: () => fetchCases(PAGE_SIZE, allVersions, page * PAGE_SIZE),
  });

  const take = useMutation({
    mutationFn: (row: CaseRow) => downloadCase(row.id, row.filename ?? `кейс-${row.id}.pdf`),
    onMutate: (row: CaseRow) => {
      setError(null);
      setBusyId(row.id);
    },
    onSuccess: saveFile,
    onError: (failure: unknown) => setError(failureText(failure, 'кейс не скачался')),
    onSettled: () => setBusyId(null),
  });

  return (
    <Stack gap="md">
      {/* Свежая версия проекта отвечает на вопрос «что отправить клиенту».
          История нужна реже — поэтому она за тумблером, а не в списке. */}
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          {allVersions ? 'Все собранные версии' : 'Свежий кейс каждого проекта'}
        </Text>
        {/* Смена тумблера возвращает на первую страницу: список становится
            другой длины, и третья страница прежнего в новом может не
            существовать вовсе. */}
        <Switch
          size="sm"
          label="показать все версии"
          checked={allVersions}
          onChange={(event) => {
            const all = event.currentTarget.checked;
            setAllVersions(all);
            setPage(0);
            // Одной правкой адреса: тумблер меняет длину списка, и страницу
            // надо сбросить тем же движением, иначе второй вызов перетрёт
            // первый — он читает параметры такими, какими они были до правки.
            screen.set({ версии: all ? 'да' : null, page: null });
          }}
        />
      </Group>

      {cases.isPending && <Text size="sm">Загружаем библиотеку…</Text>}

      {cases.isError && (
        <Alert color="red" variant="light">
          <Text size="sm">{failureText(cases.error, 'библиотека не загрузилась')}</Text>
        </Alert>
      )}

      {cases.data && cases.data.length === 0 && (
        <Alert color="yellow" variant="light">
          <Text size="sm">
            Кейсов ещё нет. Они собираются по классифицированным проектам — «Пересобрать кейсы»
            соберёт их по текущим вердиктам.
          </Text>
        </Alert>
      )}

      {cases.data && cases.data.length > 0 && (
        <CasesTable rows={cases.data} busyId={busyId} onDownload={(row) => take.mutate(row)} />
      )}

      <LibraryPager rows={cases.data} page={page} onChange={setPage} />

      {error && (
        <Alert color="red" variant="light">
          <Text size="sm">{error}</Text>
        </Alert>
      )}
    </Stack>
  );
}

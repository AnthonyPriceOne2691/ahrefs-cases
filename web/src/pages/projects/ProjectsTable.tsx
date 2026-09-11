/**
 * Таблица проектов. Колонки — то, по чему человек ищет глазами.
 *
 * Строка ведёт на карточку: вердикт с объяснением и кривые живут там, а в
 * таблице стоит ориентир — группа и счёт.
 */
import { Table, Text } from '@mantine/core';
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import type { ColumnDef } from '@tanstack/react-table';
import { useMemo } from 'react';

import type { ProjectRow } from '../../api/types';
import { months, num } from '../format';

import { GroupBadge } from './GroupBadge';

export function ProjectsTable({
  rows,
  onOpen,
}: {
  rows: ProjectRow[];
  onOpen: (project: ProjectRow) => void;
}) {
  const columns = useMemo<ColumnDef<ProjectRow>[]>(
    () => [
      { accessorKey: 'domain', header: 'Домен' },
      { accessorKey: 'niche', header: 'Ниша' },
      { accessorKey: 'geo', header: 'Гео' },
      {
        id: 'period',
        header: 'Период работ',
        cell: ({ row }) => months(row.original.period_start, row.original.period_end),
      },
      {
        id: 'group',
        header: 'Группа',
        cell: ({ row }) => <GroupBadge group={row.original.group} />,
      },
      {
        id: 'score',
        header: 'Счёт',
        cell: ({ row }) =>
          // Округляем: счёт — ориентир для сравнения строк, и «4 189,936»
          // в таблице читается как точность, которой у него нет.
          row.original.score === null ? '—' : num(row.original.score),
      },
      {
        id: 'publishable',
        header: 'Публикация',
        cell: ({ row }) => (
          <Text size="sm">{row.original.publishable ? 'можно' : 'без названия'}</Text>
        ),
      },
    ],
    [],
  );

  const table = useReactTable({ data: rows, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <Table.ScrollContainer minWidth={720}>
      <Table striped highlightOnHover>
        <Table.Thead>
          {table.getHeaderGroups().map((group) => (
            <Table.Tr key={group.id}>
              {group.headers.map((header) => (
                <Table.Th key={header.id}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </Table.Th>
              ))}
            </Table.Tr>
          ))}
        </Table.Thead>
        <Table.Tbody>
          {table.getRowModel().rows.map((row) => (
            <Table.Tr
              key={row.id}
              onClick={() => onOpen(row.original)}
              style={{ cursor: 'pointer' }}
            >
              {row.getVisibleCells().map((cell) => (
                <Table.Td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </Table.Td>
              ))}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

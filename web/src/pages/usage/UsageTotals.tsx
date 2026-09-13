/**
 * Четыре числа расхода и то, что из них следует.
 *
 * Вынесено из экрана, когда чисел стало четыре: у страницы набралась
 * цикломатическая сложность 12 при пороге 10, и это правильный сигнал — читать
 * вперемешку загрузку, ошибку и арифметику остатка уже неудобно.
 *
 * Резерв отдельным числом: он удерживает units идущего прогона, и без него
 * остаток выглядит больше, чем есть. Неучтённый расход — тоже отдельным, а не
 * вычетом из остатка: остаток обязан совпадать с кабинетом Ahrefs, иначе
 * расхождение читалось бы как ошибка сервиса. Прогон при этом считается по
 * разнице — её экран и называет словами.
 */
import { Badge, Group, Text } from '@mantine/core';

import type { UsageView } from '../../api/types';
import { num } from '../format';

/** Что показать про отставание счётчика. Пустая строка — показывать нечего. */
function lagNote(usage: UsageView): string {
  if (usage.uncounted <= 0) return '';
  if (usage.remaining === null) {
    return `Счётчик Ahrefs отстаёт: ${num(usage.uncounted)} units уже потрачены, но в его ответе их ещё нет.`;
  }
  return `Прогон считается по остатку ${num(usage.remaining - usage.uncounted)} units: счётчик Ahrefs обновляется не сразу, и свежий расход в его ответе ещё не учтён.`;
}

export function UsageTotals({ usage }: { usage: UsageView }) {
  const lag = lagNote(usage);

  return (
    <>
      <Group gap="xs">
        <Badge size="lg" variant="light" color="grape" data-usage="spent">
          потрачено {num(usage.spent)}
        </Badge>
        <Badge size="lg" variant="light" color="gray" data-usage="reserved">
          удержано резервом {num(usage.reserved)}
        </Badge>
        <Badge size="lg" variant="light" data-usage="remaining">
          остаток {usage.remaining === null ? 'неизвестен' : num(usage.remaining)}
        </Badge>
        {usage.uncounted > 0 && (
          <Badge size="lg" variant="light" color="orange" data-usage="uncounted">
            счётчик Ahrefs ещё не видит {num(usage.uncounted)}
          </Badge>
        )}
      </Group>
      {lag && (
        <Text size="sm" data-usage="trustworthy">
          {lag}
        </Text>
      )}
      <Text size="sm">
        {usage.per_hundred_domains === null
          ? 'Стоимость запуска на сто доменов пока не из чего вывести: прогонов не было.'
          : `Стоимость запуска на сто доменов по факту: ${num(usage.per_hundred_domains)} units.`}
      </Text>
    </>
  );
}

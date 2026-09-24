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
 *
 * «Потрачено» — только живые прогоны. Условные units fixture-прогонов сервис
 * считает той же формулой, но в Ahrefs они не ходили: экран называет их
 * отдельной строкой и словами, а не складывает с настоящими (Z38).
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

/**
 * Условные units — гипотетическая величина, и она называет свою гипотезу.
 * Пустая строка — fixture-прогонов с тратой не было.
 */
function conditionalNote(usage: UsageView): string {
  if (usage.conditional <= 0) return '';
  return `Условные units: ${num(usage.conditional)} — столько стоили бы прогоны без живого ключа (fixture), если бы ходили в Ahrefs. Это не расход: ни в «потрачено», ни в стоимость на сто доменов они не входят.`;
}

/** Стоимость на сто доменов — с числами, из которых она выведена. */
function perHundredNote(usage: UsageView): string {
  if (usage.per_hundred_domains === null) {
    return 'Стоимость запуска на сто доменов по факту пока не из чего вывести: живых прогонов с расходом ещё не было.';
  }
  return `Стоимость запуска на сто доменов по факту: ${num(usage.per_hundred_domains)} units (потрачено ${num(usage.spent)} units, оплачено доменов — ${num(usage.live_domains)}).`;
}

export function UsageTotals({ usage }: { usage: UsageView }) {
  const lag = lagNote(usage);
  const conditional = conditionalNote(usage);

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
      {conditional && (
        <Text size="sm" data-usage="conditional">
          {conditional}
        </Text>
      )}
      <Text size="sm" data-usage="per-hundred">
        {perHundredNote(usage)}
      </Text>
    </>
  );
}

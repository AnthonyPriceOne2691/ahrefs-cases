/**
 * Переключатель темы: значок внизу бокового меню.
 *
 * Значком, а не выпадающим списком из трёх значений («системная / светлая /
 * тёмная»): выбор здесь бинарный, а список Mantine в jsdom раскрывается
 * секундами и уводит тест в таймаут. Один значок — одно действие.
 *
 * Показывается ДЕЙСТВУЮЩАЯ тема, а не хранимая: хранимой может быть `auto`, и
 * значок «авто» не отвечает на вопрос «что я сейчас вижу». Поэтому
 * `useComputedColorScheme` — он разворачивает `auto` в то, что реально на
 * экране.
 *
 * Рисунок значка обещает РЕЗУЛЬТАТ нажатия, а не текущее состояние: в тёмной
 * теме солнце («станет светло»), в светлой луна («станет темно»). Подпись
 * `aria-label` говорит то же словами — и ею же кнопку находит тест.
 *
 * `getInitialValueInEffect: false` — тоже не мелочь: со значением по умолчанию
 * первый кадр рисуется догадкой `light`, и на тёмной теме значок успевает
 * мигнуть луной, а тест видит не ту подпись, что человек.
 */
import { ActionIcon, useComputedColorScheme, useMantineColorScheme } from '@mantine/core';
import { IconMoon, IconSun } from '@tabler/icons-react';

export function ThemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme('dark', { getInitialValueInEffect: false });

  const dark = computed === 'dark';
  const label = dark ? 'светлая тема' : 'тёмная тема';

  return (
    <ActionIcon
      variant="subtle"
      color="gray"
      size="lg"
      aria-label={label}
      title={label}
      data-shell="theme"
      onClick={() => setColorScheme(dark ? 'light' : 'dark')}
    >
      {dark ? <IconSun size={18} stroke={1.5} /> : <IconMoon size={18} stroke={1.5} />}
    </ActionIcon>
  );
}

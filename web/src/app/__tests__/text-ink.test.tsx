/**
 * Цвет `Text`: без пропса он наследуется от родителя — и чужой переменной не берёт.
 *
 * У `Text` Mantine цвет — `color: var(--text-color)` без запасного значения, а
 * переменную компонент ставит себе только при пропсе `color`. Custom property
 * наследуется, поэтому определение `--text-color` выше по дереву перекрашивает
 * каждый `Text` без пропса. Так и вышло у владельца 24.09.2026: расширение
 * браузера определяло переменную на всю страницу, и в тёмной теме абзацы,
 * плашки и значения порогов стали чёрными на тёмном стекле.
 *
 * Каскад jsdom не считает, поэтому здесь проверяется щит — то, что `Text` сам
 * ставит себе переменную. Что щит держит цвет на экране, проверено в браузере
 * (verify-report поставки `text-keeps-its-ink-in-any-browser`).
 */
import { Text } from '@mantine/core';
import { screen } from '@testing-library/react';
import type { CSSProperties, ReactNode } from 'react';
import { describe, expect, it } from 'vitest';

import { renderApp } from '../../test/render';

/** Переменная, определённая выше по дереву, — так её ставит расширение браузера. */
function underLeak(children: ReactNode) {
  return <div style={{ '--text-color': '#000' } as CSSProperties}>{children}</div>;
}

function textColorVar(text: string): string {
  return screen.getByText(text).style.getPropertyValue('--text-color');
}

describe('цвет текста', () => {
  it('текст без цвета не берёт чужую переменную', () => {
    renderApp(underLeak(<Text>Прогонов ещё не было</Text>));
    // `currentColor` в свойстве `color` означает «как у родителя»: ровно то,
    // что Mantine задумывал, оставляя переменную неопределённой.
    expect(textColorVar('Прогонов ещё не было')).toBe('currentColor');
  });

  it('цвет из пропса щит не перекрывает', () => {
    renderApp(underLeak(<Text color="red">отказ</Text>));
    expect(textColorVar('отказ')).toBe('var(--mantine-color-red-filled)');
  });

  it('приглушённый текст остаётся приглушённым', () => {
    renderApp(underLeak(<Text c="dimmed">не задано</Text>));
    expect(screen.getByText('не задано').style.color).toBe('var(--mantine-color-dimmed)');
  });
});

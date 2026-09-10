import { createTheme, rem } from '@mantine/core';

/**
 * Тема Mantine поверх токенов liquid glass (`styles/glass.css`).
 *
 * Раскладка и компоненты повторяют CMS линкбилдинга — там это отлаженное
 * поведение таблиц, форм и состояний загрузки. Цвета и поверхности приходят из
 * визуального языка local-web-agent: акцент индиго-фиолет совпадает у обоих,
 * поэтому палитры сошлись без насилия.
 */
export const glassTheme = createTheme({
  primaryColor: 'indigo',
  defaultRadius: 'md',
  fontFamily:
    'ui-sans-serif, -apple-system, "SF Pro Text", Inter, "Segoe UI", system-ui, sans-serif',
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
  headings: {
    fontWeight: '600',
    sizes: {
      h1: { fontSize: rem(28), lineHeight: '1.25' },
      h2: { fontSize: rem(22), lineHeight: '1.3' },
      h3: { fontSize: rem(18), lineHeight: '1.35' },
    },
  },
  defaultGradient: { from: 'indigo.6', to: 'violet.6', deg: 135 },
  components: {
    Paper: {
      defaultProps: { radius: 'lg', withBorder: false },
    },
    Button: {
      defaultProps: { size: 'sm' },
    },
    TextInput: {
      defaultProps: { size: 'sm' },
    },
    Select: {
      defaultProps: { size: 'sm' },
    },
  },
});

/** Цвет группы проекта. Один источник: подписи, бейджи и графики берут отсюда. */
export const groupInk = {
  good: 'var(--status-mint-ink)',
  medium: 'var(--status-amber-ink)',
  poor: 'var(--status-rose-ink)',
  insufficient_data: 'var(--ink-faint)',
} as const;

/**
 * Окружение тестов: jsdom не умеет того, на что рассчитывает Mantine.
 *
 * `matchMedia` и `ResizeObserver` в jsdom отсутствуют, а компоненты Mantine
 * спрашивают их при первом рендере. Без заглушек падает не проверяемое
 * поведение, а сам рендер — то есть тест краснеет по причине окружения.
 */
import '@testing-library/jest-dom/vitest';

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (!('ResizeObserver' in window)) {
  (window as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverStub;
}

if (!window.scrollTo) {
  window.scrollTo = () => {};
}

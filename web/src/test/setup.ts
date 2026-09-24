/**
 * Окружение тестов: jsdom не умеет того, на что рассчитывает Mantine.
 *
 * `matchMedia` и `ResizeObserver` в jsdom отсутствуют, а компоненты Mantine
 * спрашивают их при первом рендере. Без заглушек падает не проверяемое
 * поведение, а сам рендер — то есть тест краснеет по причине окружения.
 */
import '@testing-library/jest-dom/vitest';
import { beforeEach } from 'vitest';

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

/**
 * Каждый тест начинается с чистого адреса.
 *
 * Состояние экранов живёт в адресе (`app/screenState.ts`), а `window.location`
 * в jsdom один на файл: отфильтровавший тест оставлял бы следующему свои
 * параметры, и тот краснел бы по причине соседа. Так уже случилось на экране
 * пользователей: раскрытый человек оставался в адресе, следующий тест кликал
 * по той же строке — и **сворачивал** панель вместо того, чтобы раскрыть.
 */
beforeEach(() => {
  window.history.replaceState({}, '', '/');
  // Та же причина для памяти браузера: открытые окна запоминаются и там
  // (`app/stickyFlag.ts`, L182), и окно, открытое соседним тестом, всплывало
  // бы в следующем — два диалога вместо одного. Пока окно было одно, это
  // пряталось: тесты открывали то же самое окно (найдено с B6, 24.09.2026).
  localStorage.clear();
});

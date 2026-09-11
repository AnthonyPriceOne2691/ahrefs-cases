/** Рендер с провайдерами, без которых компоненты Mantine не живут. */
import { MantineProvider } from '@mantine/core';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';

import { glassTheme } from '../theme';

export function renderApp(ui: ReactElement) {
  return render(<MantineProvider theme={glassTheme}>{ui}</MantineProvider>);
}

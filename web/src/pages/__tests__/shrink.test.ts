/**
 * Ужатие скрина до отправки — пример приёмки M64 поставки `screenshots-screen`.
 *
 * Холста и `createImageBitmap` в jsdom нет: их подменяют, и проверяется своё —
 * когда ужимать, до какого размера и что делать, если не ужалось. Как браузер
 * кодирует JPEG, проверяет живой проход на стенде.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { TooBigError, fitForUpload } from '../card/shrink';

const LIMITS = { maxBytes: 2_621_440, maxSide: 2000 };

function bytes(size: number): Blob {
  return new Blob([new Uint8Array(size)], { type: 'image/png' });
}

/** Браузер с холстом: снимок 4000 × 3000, JPEG на выходе — заданного размера. */
function browser(encodedSize: number) {
  const drawn: number[][] = [];
  vi.stubGlobal(
    'createImageBitmap',
    vi.fn(async () => ({ width: 4000, height: 3000, close: vi.fn() })),
  );
  const context = {
    fillStyle: '',
    fillRect: vi.fn(),
    drawImage: vi.fn((_image: unknown, ...box: number[]) => drawn.push(box)),
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
  const toBlob = vi
    .spyOn(HTMLCanvasElement.prototype, 'toBlob')
    .mockImplementation((done: BlobCallback) => done(bytes(encodedSize)));
  return { drawn, toBlob, context };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ужатие скрина до отправки', () => {
  it('M64: файл в пределе уходит как есть, холст не трогается', async () => {
    const small = bytes(1024);
    const { toBlob } = browser(10);

    expect(await fitForUpload(small, LIMITS)).toBe(small);
    expect(toBlob).not.toHaveBeenCalled();
  });

  it('M64: больше предела — длинная сторона 2000, JPEG на белом', async () => {
    const { drawn, toBlob, context } = browser(400_000);

    const shrunk = await fitForUpload(bytes(3_000_000), LIMITS);

    expect(shrunk.size).toBe(400_000);
    expect(drawn).toEqual([[0, 0, 2000, 1500]]);
    expect(context.fillStyle).toBe('#ffffff');
    expect(toBlob.mock.calls[0]?.[1]).toBe('image/jpeg');
  });

  it('M64: и после ужатия больше предела — отказ словами, отправлять нечего', async () => {
    browser(2_800_000);

    await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(TooBigError);
    await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(/больше 2,5 МБ/);
  });

  it('M64: не картинка — отказ словами, а не ошибка браузера', async () => {
    vi.stubGlobal(
      'createImageBitmap',
      vi.fn(async () => Promise.reject(new Error('decode'))),
    );

    await expect(fitForUpload(bytes(3_000_000), LIMITS)).rejects.toThrow(
      'файл не открылся как картинка — нужен PNG, JPEG или WebP',
    );
  });
});

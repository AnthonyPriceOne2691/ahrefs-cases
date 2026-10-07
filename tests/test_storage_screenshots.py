"""Скриншоты на диске: что принимается, во что перекодируется и где лежит.

Примеры приёмки поставки `screenshots-storage`: M41 (PNG, JPEG и WebP приняты и
перекодированы), M42 (не картинка — отказ словами), M43 (огромная площадь —
отказ до распаковки), M44 (длинная сторона ужата до 2000), M45 (метаданные сняты),
M46 (прозрачное — на белом), M47 (файл кладётся под нашим именем и не уводит из
каталога).

Картинки собираются в памяти: файлы в репозитории гейт крупных файлов не пустит,
а сгенерированная картинка говорит, что проверяется, прямо в тесте.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ahrefs_cases.storage.screenshots import (
    MAX_SIDE,
    ScreenshotRejectedError,
    prepare,
    read,
    remove,
    remove_project,
    save,
)


def _image(size: tuple[int, int], fmt: str, mode: str = "RGB", **params: object) -> bytes:
    buffer = BytesIO()
    Image.new(mode, size, "white" if mode != "RGBA" else (0, 0, 0, 0)).save(
        buffer, format=fmt, **params
    )
    return buffer.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP"])
def test_three_formats_are_accepted_and_reencoded(fmt: str) -> None:
    """M41: формат определяется содержимым; на выходе — PNG или JPEG, размеры прежние."""
    prepared = prepare(_image((640, 400), fmt))

    assert prepared.mime in {"image/png", "image/jpeg"}
    assert (prepared.width, prepared.height) == (640, 400)
    assert len(prepared.checksum) == 64
    assert Image.open(BytesIO(prepared.content)).format in {"PNG", "JPEG"}


@pytest.mark.parametrize(
    "raw",
    [b"%PDF-1.7 not an image", "просто текст".encode(), _image((10, 10), "GIF", mode="P")],
)
def test_not_a_screenshot_is_refused_in_words(raw: bytes) -> None:
    """M42: PDF, текст и GIF — не скриншот; отказ называет форматы, которые нужны."""
    with pytest.raises(ScreenshotRejectedError, match="PNG, JPEG или WebP"):
        prepare(raw)


def test_huge_area_is_refused_before_decoding() -> None:
    """M43: 9000 × 5000 — отказ по заголовку, до распаковки пикселей."""
    with pytest.raises(ScreenshotRejectedError, match="9000 × 5000"):
        prepare(_image((9000, 5000), "PNG", mode="1"))


def test_long_side_is_shrunk_to_fit_the_sheet() -> None:
    """M44: 3000 × 1500 → 2000 × 1000; пропорции сохранены."""
    prepared = prepare(_image((3000, 1500), "PNG"))

    assert (prepared.width, prepared.height) == (MAX_SIDE, MAX_SIDE // 2)


def test_metadata_does_not_travel() -> None:
    """M45: EXIF (автор, камера) на лист и в бэкап не едет."""
    exif = Image.Exif()
    exif[0x013B] = "Пётр"  # Artist
    prepared = prepare(_image((320, 200), "JPEG", exif=exif.tobytes()))

    assert not Image.open(BytesIO(prepared.content)).getexif()


def test_transparency_lands_on_white() -> None:
    """M46: прозрачный PNG — на белом листе, без канала прозрачности."""
    prepared = prepare(_image((50, 50), "PNG", mode="RGBA"))

    with Image.open(BytesIO(prepared.content)) as image:
        assert image.mode == "RGB"
        assert image.getpixel((10, 10)) == (255, 255, 255)


def test_file_lives_under_our_name_inside_the_folder(tmp_path: Path) -> None:
    """M47: ключ — `<проект>/<uuid>.<расширение>`; чтение, удаление и выход из каталога."""
    prepared = prepare(_image((100, 60), "PNG"))

    key = save(tmp_path, 7, prepared)

    assert key.startswith("7/") and key.endswith(".png")
    assert read(tmp_path, key) == prepared.content
    assert not list((tmp_path / "7").glob(".*.part"))
    assert remove(tmp_path, key) is True
    assert remove(tmp_path, key) is False
    with pytest.raises(ScreenshotRejectedError):
        read(tmp_path, "../outside.png")


def test_project_folder_goes_with_the_project(tmp_path: Path) -> None:
    """M47: удаление проекта уносит его каталог скриншотов и только его."""
    prepared = prepare(_image((100, 60), "PNG"))
    save(tmp_path, 7, prepared)
    save(tmp_path, 7, prepare(_image((120, 60), "PNG")))
    neighbour = save(tmp_path, 8, prepared)

    assert remove_project(tmp_path, 7) == 2
    assert not (tmp_path / "7").exists()
    assert read(tmp_path, neighbour) == prepared.content
    assert remove_project(tmp_path, 7) == 0

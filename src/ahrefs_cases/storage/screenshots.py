"""Скриншоты проектов на диске: проверить, что пришла картинка, ужать и сложить.

Скрин загружает человек, а печатает лист PDF, поэтому байтам на входе не верим:
формат определяется содержимым (имя файла и заголовок `Content-Type` присылает
браузер), размер проверяется до распаковки — картинка-«бомба» в 30 000 × 30 000
занимает килобайты, а распакованная — гигабайты. Принятое перекодируется заново:
метаданные (EXIF с геометкой, имя автора) на лист и в бэкап не едут, а длинная
сторона ужимается до той, что ещё читается на листе A4.

Файл кладётся под именем, которое придумали мы (`<проект>/<uuid>.png`), сначала
во временный файл и затем переименованием: прерванная запись не оставляет
половину картинки под настоящим именем. Каталог — внутри `data/`, его целиком
забирает ночной бэкап.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

FORMATS = ("PNG", "JPEG", "WEBP")
MAX_SIDE = 2000
"""Длинная сторона после ужатия: на A4 при 200 dpi в ширину помещается ~1600 px."""

MAX_PIXELS = 40_000_000
"""Предел площади до распаковки — с запасом под широкий монитор, далеко от бомбы."""

PNG_LIMIT = 1_500_000
"""PNG тяжелее этого перекодируется в JPEG: снимок с градиентами в PNG раздувает PDF."""


class ScreenshotRejectedError(ValueError):
    """Картинка не принята — словами для человека."""


@dataclass(frozen=True, slots=True)
class PreparedImage:
    content: bytes
    mime: str
    width: int
    height: int
    checksum: str


def prepare(raw: bytes) -> PreparedImage:
    """Сырые байты → ужатая картинка без метаданных или отказ словами."""
    try:
        with Image.open(BytesIO(raw), formats=FORMATS) as source:
            width, height = source.size
            if width * height > MAX_PIXELS:
                message = f"картинка {width} × {height} слишком большая для скриншота"
                raise ScreenshotRejectedError(message)
            source.load()
            image = _flat(ImageOps.exif_transpose(source))
    except UnidentifiedImageError as exc:
        raise ScreenshotRejectedError("это не картинка PNG, JPEG или WebP") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ScreenshotRejectedError("картинка слишком большая для скриншота") from exc
    except OSError as exc:
        raise ScreenshotRejectedError("картинка повреждена: прочитать её не удалось") from exc
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    content, mime = _encode(image)
    return PreparedImage(
        content=content,
        mime=mime,
        width=image.width,
        height=image.height,
        checksum=hashlib.sha256(content).hexdigest(),
    )


STORED = {"image/png": "PNG", "image/jpeg": "JPEG"}
"""Во что `prepare` перекодирует: тип в базе → формат файла на диске."""


def ensure_intact(content: bytes, mime: str) -> None:
    """Картинка целая и того типа, что записан в базе; иначе — отказ словами.

    `verify` Pillow ловит битую контрольную сумму PNG, а JPEG не проверяет вовсе:
    обрезанный JPEG проходит его и молча пропадает с листа при рендере. Поэтому
    картинка ещё и распаковывается целиком — после `verify` её надо открыть заново.
    """
    fmt = STORED.get(mime)
    if fmt is None:
        message = f"скриншот типа {mime!r} не из тех, что мы храним"
        raise ScreenshotRejectedError(message)
    try:
        with Image.open(BytesIO(content), formats=(fmt,)) as image:
            image.verify()
        with Image.open(BytesIO(content), formats=(fmt,)) as image:
            image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ScreenshotRejectedError("картинка повреждена: прочитать её не удалось") from exc


def _flat(image: Image.Image) -> Image.Image:
    """Прозрачное — на белый лист; остальное — в RGB."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        sheet = Image.new("RGB", rgba.size, (255, 255, 255))
        sheet.paste(rgba, mask=rgba.getchannel("A"))
        return sheet
    return image.convert("RGB")


def _encode(image: Image.Image) -> tuple[bytes, str]:
    png = BytesIO()
    image.save(png, format="PNG", optimize=True)
    if png.tell() <= PNG_LIMIT:
        return png.getvalue(), "image/png"
    jpeg = BytesIO()
    image.save(jpeg, format="JPEG", quality=88, optimize=True)
    return jpeg.getvalue(), "image/jpeg"


def save(root: Path, project_id: int, image: PreparedImage) -> str:
    """Положить картинку на диск и вернуть её ключ — путь внутри каталога скриншотов."""
    suffix = "png" if image.mime == "image/png" else "jpg"
    key = f"{project_id}/{uuid4().hex}.{suffix}"
    target = root / key
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f".{target.name}.part")
    partial.write_bytes(image.content)
    os.replace(partial, target)
    return key


def read(root: Path, key: str) -> bytes:
    """Байты картинки по ключу из базы. Ключ уводит из каталога — отказ, а не чтение."""
    return _inside(root, key).read_bytes()


def remove(root: Path, key: str) -> bool:
    """Стереть файл скриншота; нет файла — не беда, но в журнал."""
    try:
        _inside(root, key).unlink()
    except FileNotFoundError:
        logger.warning("screenshot_file_missing", extra={"key": key})
        return False
    return True


def remove_project(root: Path, project_id: int) -> int:
    """Стереть каталог скриншотов проекта после его удаления. Сколько файлов ушло."""
    folder = _inside(root, str(project_id))
    if not folder.is_dir():
        return 0
    count = sum(1 for item in folder.iterdir() if item.is_file())
    shutil.rmtree(folder)
    return count


def _inside(root: Path, key: str) -> Path:
    base = root.resolve()
    path = (base / key).resolve()
    if path == base or not path.is_relative_to(base):
        message = f"путь скриншота вне каталога: {key}"
        raise ScreenshotRejectedError(message)
    return path

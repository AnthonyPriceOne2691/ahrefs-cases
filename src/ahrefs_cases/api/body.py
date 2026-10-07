"""Тело запроса с пределом по ходу чтения — одно на все загрузки.

Файл списка и скриншот приходят сырым телом, а не multipart: ради одного поля
`python-multipart` был бы зависимостью без пользы. Предел проверяется **по ходу
чтения**, а не по `Content-Length`: заголовок присылает клиент, и доверять ему —
значит принять тело любого размера от того, кто соврал. Поток обрывается на
пределе — лишние байты в память не попадают.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status


async def read_body(request: Request, *, limit: int, too_large: str, empty: str) -> bytes:
    """Тело целиком, не больше `limit` байт; больше — 413, пусто — 400, словами вызывающего."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=too_large)
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=empty)
    return body

"""Заголовки безопасности держатся устройством конфига, а не памятью автора.

Главная ловушка nginx: `add_header` наследуется в location, ТОЛЬКО пока у того
нет ни одного своего. Любой location со своим заголовком (кэш у /assets/ и у
документа) молча теряет все общие — ответ выглядит нормально, и заметить
пропажу можно только, сравнив заголовки глазами. Поэтому правило проверяется
чтением конфига: у каждого такого location обязан быть include сниппета.

Вторая ловушка — CSP: встроенный <script> в index.html исполняется, только если
его sha256 есть в политике. Появится такой скрипт без хеша — страница ломается
тихо, в консоли браузера.
"""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONF = (ROOT / "deploy" / "nginx.conf").read_text(encoding="utf-8")
SNIPPET = "include /etc/nginx/snippets/security-headers.conf;"


LOCATION = re.compile(r"^[ \t]*location[ \t]+([^{\n]+)\{([^}]*)\}", re.MULTILINE)
"""Директива — с начала строки: слово «location» в комментарии блоком не является,
а без привязки регулярка съедала текст от комментария до следующего блока."""


def _locations(conf: str) -> dict[str, str]:
    """Тело каждого location — по его заголовку. Вложенных блоков в конфиге нет."""
    return {match.group(1).strip(): match.group(2) for match in LOCATION.finditer(conf)}


def _server_level(conf: str) -> str:
    """Директивы server-блока без тел location."""
    return LOCATION.sub("", conf)


def test_every_location_with_own_header_repeats_the_snippet() -> None:
    offenders = [
        name
        for name, body in _locations(CONF).items()
        if "add_header" in body and SNIPPET not in body
    ]
    assert not offenders, f"location теряют общие заголовки: {offenders}"


def test_snippet_is_on_the_server_level_and_in_the_image() -> None:
    assert SNIPPET in _server_level(CONF)
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "deploy/security-headers.conf /etc/nginx/snippets/security-headers.conf" in dockerfile


def test_server_version_is_not_announced() -> None:
    assert "server_tokens off;" in _server_level(CONF)
    proxy = (ROOT / "deploy" / "proxy" / "ahrefs-cases.conf").read_text(encoding="utf-8")
    assert "server_tokens off;" in proxy


def test_document_has_csp_and_every_inline_script_is_hashed() -> None:
    document = _locations(CONF)["= /index.html"]
    policy = re.search(r'Content-Security-Policy\s+"([^"]+)"', document)
    assert policy is not None, "у документа нет CSP"
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    inline = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", index, flags=re.DOTALL)
    for body in inline:
        digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
        assert f"'sha256-{digest}'" in policy.group(1), (
            f"встроенный скрипт index.html не разрешён политикой: добавь 'sha256-{digest}'"
        )

#!/usr/bin/env bash
# Пересобрать uv.lock — зафиксированные версии зависимостей Python (Z48).
#
# Образ и CI ставят ровно то, что записано в uv.lock, с хешами: `uv export
# --locked` переводит его в список для pip и падает, если pyproject.toml правили
# без пересборки lock. Поэтому правка зависимостей в pyproject.toml идёт вместе
# с запуском этого скрипта и коммитом uv.lock.
#
#   scripts/lock_deps.sh                            # после правки pyproject.toml
#   scripts/lock_deps.sh --upgrade-package fastapi  # поднять один пакет
#   scripts/lock_deps.sh --upgrade                  # поднять всё — отдельной поставкой
#
# Без флагов версии не поднимаются: записанные uv берёт как предпочтение и
# меняет только то, чего требует правка pyproject.toml.
#
# Версия uv — из `[tool.uv] required-version`: её же ставят Dockerfile и CI, и
# lock, записанный другой версией, там могут счесть устаревшим. На машине нужен
# uv любой версии — нужную он скачает сам.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uvx >/dev/null 2>&1; then
  echo "нужен uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

version="$(sed -n 's/^required-version = "==\(.*\)"$/\1/p' pyproject.toml)"
if [ -z "$version" ]; then
  echo "в pyproject.toml нет [tool.uv] required-version = \"==X.Y.Z\"" >&2
  exit 1
fi

uvx "uv@$version" lock "$@"

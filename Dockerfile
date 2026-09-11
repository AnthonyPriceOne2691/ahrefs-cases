# Системные библиотеки WeasyPrint кладутся уже здесь, хотя PDF появится в Ф4:
# иначе Ф4 начнётся с отладки образа, а не со сборки кейса.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Питон, режим разработки -------------------------------------------------
# Исходники приезжают монтированием (см. компоуз), а не слоем образа: правка в
# редакторе обязана подхватываться без пересборки. В образ кладётся то, без чего
# контейнер не стартует вовсе.
FROM base AS dev
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[dev]"
COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY scripts ./scripts

# --- Питон, боевой режим -----------------------------------------------------
FROM base AS prod
COPY pyproject.toml README.md ./
COPY src ./src
# `build/` — след setuptools: копия исходников, оставшаяся после установки.
# Удаляется тем же слоем, иначе так и лежит в образе лишними 864 КБ — мелочь,
# но ровно того же рода, что `.venv` в контексте сборки (урок L69).
RUN pip install "." && rm -rf build
COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
COPY scripts ./scripts

# --- Фронт, режим разработки -------------------------------------------------
# Зависимости ставятся в образе и живут в томе (см. компоуз): каталог
# `node_modules`, собранный на машине разработчика, в Linux-контейнере
# неработоспособен — там бинарники под другую систему.
#
# Версия прибита цифрой нарочно: обновление node — отдельное решение, а не
# побочный эффект пересборки в другой день.
FROM node:22-slim AS web-dev
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
CMD ["npm", "run", "dev"]

# --- Фронт, сборка -----------------------------------------------------------
# Отдельная стадия: инструменты сборки (node, npm, 372 МБ зависимостей) в боевой
# образ не попадают — туда едут только получившиеся файлы.
FROM node:22-slim AS web-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Фронт, боевой режим -----------------------------------------------------
FROM nginx:1.27-alpine AS web
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=web-build /app/web/dist /usr/share/nginx/html

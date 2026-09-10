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

FROM base AS dev
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[dev,export]"
COPY . .

FROM base AS prod
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[export]"
COPY migrations ./migrations
COPY config ./config

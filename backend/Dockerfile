FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPLOAD_TMP_DIR=/tmp/parserly_uploads

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libmagic1 \
        libpq5 \
        libxml2 \
        libxslt1.1 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app \
    && useradd --system --gid app --create-home app

WORKDIR /app

COPY requirements.txt .
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

RUN mkdir -p "${UPLOAD_TMP_DIR}" \
    && chown app:app "${UPLOAD_TMP_DIR}" \
    && chmod 0700 "${UPLOAD_TMP_DIR}"

COPY --chown=app:app app ./app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

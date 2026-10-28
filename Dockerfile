FROM python:3.11-alpine3.23@sha256:c8d52af7e2645b587d464082ab29ff4ddc9fc514f353b4ed491b3ae8105d4200

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk upgrade --no-cache && \
    addgroup -S django && \
    adduser -S -D -H -G django django

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall --yes setuptools wheel pip

COPY . .
RUN python manage.py collectstatic --noinput && \
    chown -R django:django /app

USER django

EXPOSE 8080

ENTRYPOINT ["/app/docker/entrypoint.sh"]

#!/bin/sh
set -eu

python manage.py migrate --noinput

exec gunicorn app.wsgi:application \
    --bind 0.0.0.0:8080 \
    --workers 1 \
    --threads 4 \
    --timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --limit-request-line 4094 \
    --limit-request-fields 100 \
    --limit-request-field_size 8190 \
    --error-logfile -

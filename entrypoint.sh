#!/bin/sh
set -e

echo "Waiting for database..."

RETRIES=30
i=0
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  i=$((i + 1))
  if [ "$i" -ge "$RETRIES" ]; then
    echo "ERROR: Database not available after ${RETRIES}s. Aborting."
    exit 1
  fi
  echo "  attempt $i/$RETRIES — waiting..."
  sleep 1
done

echo "Database is up."

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec "$@"

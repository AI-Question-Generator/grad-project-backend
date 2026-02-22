#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

if [ "$DATABASE_URL" != "sqlite:////app/db.sqlite3" ]
then
    echo "Waiting for postgres..."

    # Extract host and port from DATABASE_URL
    # Format: postgres://user:password@host:port/dbname
    DB_HOST=$(echo $DATABASE_URL | awk -F'[@/:]' '{print $5}')
    DB_PORT=$(echo $DATABASE_URL | awk -F'[@/:]' '{print $6}')

    while ! pg_isready -h $DB_HOST -p $DB_PORT -U $DATABASE_USER; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

echo "Applying database migrations..."
python manage.py migrate

echo "Starting server..."
exec "$@"

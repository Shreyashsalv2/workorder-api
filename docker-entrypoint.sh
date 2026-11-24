#!/bin/sh
# Apply database migrations before starting, when a real database is configured.
set -e
if [ -n "$DATABASE_URL" ]; then
  flask db upgrade
fi
exec "$@"

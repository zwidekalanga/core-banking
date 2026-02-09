#!/bin/bash
set -e

# Only run migrations and seeding for the HTTP service (default CMD).
# Other commands (e.g., Celery workers) skip this since the HTTP service
# must be healthy before they start.
if echo "$@" | grep -q "uvicorn"; then
    echo "Running database migrations..."
    alembic upgrade head || echo "WARNING: Migrations failed — check database connectivity"

    echo "Seeding data..."
    python -m scripts.seed_data || echo "WARNING: Seeding failed — data may already exist"
fi

echo "Starting: $@"
exec "$@"

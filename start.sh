#!/bin/bash

# Start script for both web server and celery worker

# Start Celery worker in background
echo "Starting Celery worker..."
uv run --no-sync celery -A app.celery_worker:celery_app worker --loglevel=info &

# Start the web server in foreground
echo "Starting web server..."
uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
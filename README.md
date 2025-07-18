# LINE Webhook Microservice

A microservice for handling LINE webhook events and generating short URLs using FastAPI and Celery with built-in URL shortening logic.

## Features

- LINE webhook signature verification
- Asynchronous message processing with Celery
- Built-in URL shortening service with PostgreSQL database
- URL validation using Pydantic
- Automatic page title fetching
- Click tracking and analytics
- Docker containerization with PostgreSQL and Redis
- Health check endpoint

## Setup

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your LINE channel credentials and shortener API URL

3. Install dependencies with uv:
   ```bash
   uv sync
   ```

## Running with Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database
- Redis (message broker)
- FastAPI web server on port 8000
- Celery worker
- Flower monitoring on port 5555

## Running Locally

1. Start PostgreSQL and Redis:
   ```bash
   docker run -d -p 5432:5432 -e POSTGRES_DB=shortener -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password postgres:15-alpine
   docker run -d -p 6379:6379 redis:7-alpine
   ```

2. Set up environment variables:
   ```bash
   export DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/shortener
   export BROKER_URL=redis://localhost:6379/0
   ```

3. Start the web server:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

4. Start the Celery worker:
   ```bash
   uv run celery -A app.celery_worker:celery_app worker --loglevel=info
   ```

## API Endpoints

- `POST /webhook` - LINE webhook endpoint
- `GET /health` - Health check
- `POST /api/shorten` - Create short URL (JSON: `{"url": "https://example.com"}`)
- `GET /{short_code}` - Redirect to original URL

## Environment Variables

- `CHANNEL_SECRET` - LINE channel secret
- `CHANNEL_TOKEN` - LINE channel access token
- `DATABASE_URL` - PostgreSQL database URL
- `BROKER_URL` - Redis broker URL (default: redis://localhost:6379/0)

## Testing with ngrok

For development, use ngrok to expose your local server:

```bash
ngrok http 8000
```

Then set the webhook URL in LINE Console to `https://your-ngrok-id.ngrok.io/webhook`
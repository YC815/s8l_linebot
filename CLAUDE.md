# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LINE Webhook microservice for URL shortening built with Python, FastAPI, and Celery. The architecture follows a microservice pattern with asynchronous message processing and built-in URL shortening logic using PostgreSQL database.

## Development Commands

### Setup and Installation
```bash
# Copy environment configuration
cp .env.example .env

# Install dependencies using uv
uv sync
```

### Running the Service

**Docker Compose (Recommended)**
```bash
# Start all services (PostgreSQL, Redis, FastAPI, Celery worker, Flower)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Local Development**
```bash
# Start PostgreSQL and Redis
docker run -d -p 5432:5432 -e POSTGRES_DB=shortener -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Start FastAPI web server
uv run uvicorn app.main:app --reload

# Start Celery worker (in separate terminal)
uv run celery -A app.celery_worker:celery_app worker --loglevel=info

# Start Flower monitoring (optional)
uv run celery -A app.celery_worker:celery_app flower --port=5555
```

### Testing and Development
```bash
# Expose local server for LINE webhook testing
ngrok http 8000

# Check health endpoint
curl http://localhost:8000/health
```

## Architecture Overview

### Core Components

**FastAPI Web Layer** (`app/main.py`):
- Handles LINE webhook events at `/webhook`
- Performs HMAC-SHA256 signature verification
- Delegates message processing to Celery background tasks
- Returns immediate HTTP 200 response to prevent timeouts

**Celery Worker Layer** (`app/celery_worker.py`):
- Processes LINE messages asynchronously
- Validates URLs using Pydantic HttpUrl
- Creates short URLs using internal business logic
- Implements retry logic with exponential backoff
- Sends replies via LINE Bot API

**URL Shortening Logic** (`app/url_shortener.py`):
- Generates 6-character URL-safe short codes
- Validates and normalizes URLs (auto-adds https://)
- Fetches page titles with timeout and error handling
- Handles duplicate URLs and collision detection
- Stores data in PostgreSQL with click tracking

**Message Flow**:
1. LINE Platform → FastAPI webhook endpoint
2. Signature verification → Immediate HTTP 200 response
3. Event queued to Celery via Redis
4. Background worker processes message
5. URL validation → Internal short URL creation → LINE reply

### Key Design Patterns

**Async Processing**: Web layer immediately responds while background tasks handle business logic to prevent webhook timeouts.

**Service Integration**: Clean separation between LINE Bot API and internal URL shortening logic with proper error handling.

**Configuration Management**: Environment-based configuration with `.env` files and Docker environment variables.

## Required Environment Variables

```bash
CHANNEL_SECRET=your_line_channel_secret
CHANNEL_TOKEN=your_line_channel_access_token
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/shortener
BROKER_URL=redis://localhost:6379/0  # Default for local development
```

## Service Endpoints

- **POST /webhook**: LINE webhook receiver (requires valid signature)
- **GET /health**: Health check endpoint
- **POST /api/shorten**: Create short URL (JSON: `{"url": "https://example.com"}`)
- **GET /{short_code}**: Redirect to original URL (with click tracking)
- **http://localhost:5555**: Flower monitoring dashboard (when running)

## Development Notes

- The project uses `uv` as the modern Python package manager
- LINE webhook signature verification is critical for security
- Celery tasks include automatic retry mechanisms for reliability
- Error messages are localized in Traditional Chinese
- The service is designed to be stateless and horizontally scalable

## Integration Points

**External Dependencies**:
- LINE Messaging API for webhook events and replies
- PostgreSQL database for URL storage and analytics
- Redis as message broker for Celery

**Docker Services**:
- `postgres`: PostgreSQL database (port 5432)
- `redis`: Message broker with data persistence (port 6379)
- `web`: FastAPI application (port 8000)
- `worker`: Celery background worker
- `flower`: Monitoring dashboard (port 5555)

**Database Schema**:
- `urls` table: id, original_url (unique), short_code (unique), title, click_count, timestamps
- Indexes on original_url and short_code for performance
- Auto-generated UUID primary keys
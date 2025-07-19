FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy Prisma schema
COPY schema.prisma ./

# Generate Prisma Client
RUN uv run prisma generate

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Run the application (web server only, no Celery worker needed)
CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set")
    print("Available environment variables:")
    for key in sorted(os.environ.keys()):
        if 'DATABASE' in key.upper() or 'DB' in key.upper():
            print(f"  {key}={os.environ[key]}")
    raise ValueError("DATABASE_URL environment variable is required")

print(f"Using DATABASE_URL: {DATABASE_URL}")

# Convert PostgreSQL URL to async format if needed
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    print(f"Converted to: {DATABASE_URL}")

# Support other database URL formats
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    print(f"Converted postgres:// to: {DATABASE_URL}")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    """Database session dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
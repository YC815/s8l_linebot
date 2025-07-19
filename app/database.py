"""Prisma database client for the application."""
from prisma import Prisma
from typing import Optional

# Global Prisma client instance
_client: Optional[Prisma] = None

async def get_prisma_client() -> Prisma:
    """Get or create a Prisma client instance."""
    global _client
    if _client is None:
        _client = Prisma(auto_register=True)
        await _client.connect()
    return _client

async def disconnect_prisma():
    """Disconnect the Prisma client."""
    global _client
    if _client is not None:
        await _client.disconnect()
        _client = None

async def get_db():
    """FastAPI dependency for getting database client."""
    return await get_prisma_client()
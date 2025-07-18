import os
import hashlib
import hmac
import base64
from typing import List

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from dotenv import load_dotenv

from .celery_worker import process_message_task
from .database import get_db, init_db
from .url_shortener import create_short_url, get_original_url

load_dotenv()

app = FastAPI(title="LINE Webhook Microservice")

# Pydantic models
class ShortenRequest(BaseModel):
    url: str

class ShortenResponse(BaseModel):
    shortCode: str
    originalUrl: str
    title: str
    shortUrl: str

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await init_db()

CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")
CHANNEL_TOKEN = os.getenv("CHANNEL_TOKEN")

if not CHANNEL_SECRET or not CHANNEL_TOKEN:
    raise ValueError("Missing required environment variables: CHANNEL_SECRET or CHANNEL_TOKEN")

webhook_handler = WebhookHandler(CHANNEL_SECRET)

def verify_signature(body: bytes, signature: str) -> bool:
    """Verify LINE webhook signature"""
    if not signature:
        return False
    
    hash_value = hmac.new(
        CHANNEL_SECRET.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    
    expected_signature = base64.b64encode(hash_value).decode('utf-8')
    return hmac.compare_digest(signature, expected_signature)

@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle LINE webhook events"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    
    if not verify_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    try:
        events = webhook_handler.parser.parse(body.decode('utf-8'), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Process events in background
    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            print(f"[LINE MESSAGE] User: {event.source.user_id}, Message: {event.message.text}")
            background_tasks.add_task(
                process_message_task.delay,
                event.reply_token,
                event.message.text
            )
    
    return JSONResponse(content={"status": "ok"})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api/shorten", response_model=ShortenResponse)
async def shorten_url(request: ShortenRequest, db: AsyncSession = Depends(get_db)):
    """Create a short URL"""
    try:
        result = await create_short_url(db, request.url)
        return ShortenResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in shorten API: {e}")
        raise HTTPException(status_code=500, detail="伺服器錯誤，請稍後重試")

@app.get("/{short_code}")
async def redirect_url(short_code: str, db: AsyncSession = Depends(get_db)):
    """Redirect to original URL"""
    original_url = await get_original_url(db, short_code)
    if original_url:
        return RedirectResponse(url=original_url, status_code=302)
    else:
        raise HTTPException(status_code=404, detail="短網址不存在")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
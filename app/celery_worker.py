import os
import asyncio
from celery import Celery
from pydantic import HttpUrl, ValidationError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from .database import AsyncSessionLocal
from .url_shortener import create_short_url

load_dotenv()

# Initialize Celery
broker_url = os.getenv("BROKER_URL", "redis://localhost:6379/0")
celery_app = Celery("webhook_worker", broker=broker_url)

# LINE Bot API client
CHANNEL_TOKEN = os.getenv("CHANNEL_TOKEN")

if not CHANNEL_TOKEN:
    raise ValueError("Missing required environment variables: CHANNEL_TOKEN")

# Initialize LINE Bot API client
configuration = Configuration(access_token=CHANNEL_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

async def create_short_url_async(message_text: str) -> dict:
    """Create short URL using internal logic"""
    async with AsyncSessionLocal() as db:
        return await create_short_url(db, message_text)

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_message_task(self, reply_token: str, message_text: str):
    """Process incoming message and generate short URL"""
    print(f"[CELERY WORKER] Processing message: {message_text}")
    try:
        # Validate URL format using Pydantic
        try:
            validated_url = HttpUrl(message_text)
        except ValidationError:
            # Not a valid URL, send error message
            error_message = TextMessage(text="請提供有效的網址格式 (http:// 或 https://)")
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[error_message]
            )
            line_bot_api.reply_message(reply_request)
            return
        
        # Create short URL using internal logic
        try:
            result = asyncio.run(create_short_url_async(str(validated_url)))
            short_url = result.get("shortUrl")
            if short_url:
                reply_message = TextMessage(text=f"短網址: {short_url}")
                print(f"[CELERY WORKER] Generated short URL: {short_url}")
            else:
                reply_message = TextMessage(text="短網址產生失敗，請稍後再試")
                print(f"[CELERY WORKER] Failed to generate short URL for: {validated_url}")
        except ValueError as e:
            # Handle specific validation errors
            reply_message = TextMessage(text=str(e))
            print(f"[CELERY WORKER] Validation error: {e}")
        except Exception as e:
            print(f"[CELERY WORKER] Error creating short URL: {e}")
            reply_message = TextMessage(text="短網址服務暫時無法使用，請稍後再試")
        
        # Send reply via LINE
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[reply_message]
        )
        line_bot_api.reply_message(reply_request)
        
    except Exception as e:
        # Log error and send generic error message
        print(f"Error processing message: {str(e)}")
        error_message = TextMessage(text="處理請求時發生錯誤，請稍後再試")
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[error_message]
        )
        line_bot_api.reply_message(reply_request)
        raise self.retry(exc=e)
import os
import asyncio
import traceback
from celery import Celery
from pydantic import HttpUrl, ValidationError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ApiException
)
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
    print(f"[CELERY WORKER] 收到新任務: {message_text}")
    print(f"[CELERY WORKER] Reply Token: {reply_token}")

    reply_message = None

    try:
        # Validate URL format using Pydantic
        try:
            print("[CELERY WORKER] 開始驗證 URL 格式...")
            validated_url = HttpUrl(message_text)
            print(f"[CELERY WORKER] URL 驗證成功: {validated_url}")

            # Create short URL using internal logic
            print("[CELERY WORKER] 開始生成短網址...")
            result = asyncio.run(create_short_url_async(str(validated_url)))
            print(f"[CELERY WORKER] 短網址生成結果: {result}")

            short_url = result.get("shortUrl")
            if short_url:
                reply_message = TextMessage(short_url)
                print(f"[CELERY WORKER] 成功生成短網址: {short_url}")
            else:
                reply_message = TextMessage(text="短網址產生失敗，請稍後再試")
                print("[CELERY WORKER] 短網址生成失敗")

        except ValidationError as e:
            print(f"[CELERY WORKER] URL 格式驗證失敗: {e}")
            reply_message = TextMessage(text="請提供有效的網址格式 (http:// 或 https://)")

        except ValueError as e:
            print(f"[CELERY WORKER] 值錯誤: {e}")
            reply_message = TextMessage(text=str(e))

        except Exception as e:
            print(f"[CELERY WORKER] 生成短網址時發生錯誤: {e}")
            print(f"[CELERY WORKER] 錯誤詳情: {traceback.format_exc()}")
            reply_message = TextMessage(text="短網址服務暫時無法使用，請稍後再試")

        # Send reply via LINE
        print("[CELERY WORKER] 準備發送回覆訊息...")
        print(f"[CELERY WORKER] 回覆內容: {reply_message.text}")

        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[reply_message]
        )

        try:
            print("[CELERY WORKER] 正在呼叫 LINE API...")
            response = line_bot_api.reply_message(reply_request)
            print(f"[CELERY WORKER] LINE API 回覆成功: {response}")
        except ApiException as e:
            print(f"[CELERY WORKER] LINE API 錯誤: {e}")
            print(f"[CELERY WORKER] 錯誤狀態碼: {e.status}")
            print(f"[CELERY WORKER] 錯誤詳情: {e.body}")
            print(f"[CELERY WORKER] 錯誤追蹤: {traceback.format_exc()}")
            raise
        except Exception as e:
            print(f"[CELERY WORKER] 發送 LINE 訊息時發生未知錯誤: {e}")
            print(f"[CELERY WORKER] 錯誤追蹤: {traceback.format_exc()}")
            raise

        print("[CELERY WORKER] 任務完成")

    except Exception as e:
        print(f"[CELERY WORKER] 任務處理失敗: {str(e)}")
        print(f"[CELERY WORKER] 完整錯誤追蹤: {traceback.format_exc()}")

        # Try to send error message
        try:
            error_message = TextMessage(text="處理請求時發生錯誤，請稍後再試")
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[error_message]
            )
            line_bot_api.reply_message(reply_request)
        except Exception as send_error:
            print(f"[CELERY WORKER] 發送錯誤訊息也失敗: {send_error}")

        raise self.retry(exc=e)

import os
import traceback
from pydantic import HttpUrl, ValidationError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ApiException
)
from dotenv import load_dotenv

from .database import AsyncSessionLocal
from .url_shortener import create_short_url

load_dotenv()

# LINE Bot API client
CHANNEL_TOKEN = os.getenv("CHANNEL_TOKEN")

print(f"[DEBUG] CHANNEL_TOKEN length: {len(CHANNEL_TOKEN) if CHANNEL_TOKEN else 'None'}")
print(f"[DEBUG] CHANNEL_TOKEN preview: {CHANNEL_TOKEN[:20]}..." if CHANNEL_TOKEN else "No CHANNEL_TOKEN")

if not CHANNEL_TOKEN:
    raise ValueError("Missing required environment variables: CHANNEL_TOKEN")

# Initialize LINE Bot API client
configuration = Configuration(access_token=CHANNEL_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)


async def process_message_sync(reply_token: str, message_text: str):
    """Process incoming message and generate short URL synchronously"""
    print(f"[MESSAGE HANDLER] 收到新訊息: {message_text}")
    print(f"[MESSAGE HANDLER] Reply Token: {reply_token}")

    reply_message = None

    try:
        # Validate URL format using Pydantic
        try:
            print("[MESSAGE HANDLER] 開始驗證 URL 格式...")
            validated_url = HttpUrl(message_text)
            print(f"[MESSAGE HANDLER] URL 驗證成功: {validated_url}")

            # Create short URL using internal logic
            print("[MESSAGE HANDLER] 開始生成短網址...")
            async with AsyncSessionLocal() as db:
                result = await create_short_url(db, str(validated_url))
                print(f"[MESSAGE HANDLER] 短網址生成結果: {result}")

            short_url = result.get("shortUrl")
            if short_url:
                reply_message = TextMessage(text=f"{short_url}")
                print(f"[MESSAGE HANDLER] 成功生成短網址: {short_url}")
            else:
                reply_message = TextMessage(text="短網址產生失敗，請稍後再試")
                print("[MESSAGE HANDLER] 短網址生成失敗")

        except ValidationError as e:
            print(f"[MESSAGE HANDLER] URL 格式驗證失敗: {e}")

            # Check for common greetings
            greetings = ["你好", "hi", "hello", "嗨", "安安", "哈囉", "早安", "午安", "晚安"]
            help_commands = ["help", "幫助", "說明", "指令"]

            if message_text.lower() in greetings:
                reply_message = TextMessage(text="你好！歡迎使用短網址服務 📎\n\n直接傳送網址給我，我會幫您生成短網址！\n\n範例：\nhttps://www.google.com")
            elif message_text.lower() in help_commands:
                reply_message = TextMessage(text="📎 短網址服務使用說明\n\n直接傳送完整網址給我即可：\n• 支援 http:// 或 https:// 開頭\n• 例如：https://www.example.com\n\n我會立即為您生成短網址！")
            else:
                reply_message = TextMessage(text="請提供有效的網址格式 (http:// 或 https://)\n\n範例：https://www.google.com")

        except ValueError as e:
            print(f"[MESSAGE HANDLER] 值錯誤: {e}")
            reply_message = TextMessage(text=str(e))

        except Exception as e:
            print(f"[MESSAGE HANDLER] 生成短網址時發生錯誤: {e}")
            print(f"[MESSAGE HANDLER] 錯誤詳情: {traceback.format_exc()}")
            reply_message = TextMessage(text="短網址服務暫時無法使用，請稍後再試")

        # Send reply via LINE
        print("[MESSAGE HANDLER] 準備發送回覆訊息...")
        print(f"[MESSAGE HANDLER] 回覆內容: {reply_message.text}")

        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[reply_message]
        )

        try:
            print("[MESSAGE HANDLER] 正在呼叫 LINE API...")
            response = line_bot_api.reply_message(reply_request)
            print(f"[MESSAGE HANDLER] LINE API 回覆成功: {response}")
        except ApiException as e:
            print(f"[MESSAGE HANDLER] LINE API 錯誤: {e}")
            print(f"[MESSAGE HANDLER] 錯誤狀態碼: {e.status}")
            print(f"[MESSAGE HANDLER] 錯誤詳情: {e.body}")
            print(f"[MESSAGE HANDLER] 錯誤追蹤: {traceback.format_exc()}")
            raise
        except Exception as e:
            print(f"[MESSAGE HANDLER] 發送 LINE 訊息時發生未知錯誤: {e}")
            print(f"[MESSAGE HANDLER] 錯誤追蹤: {traceback.format_exc()}")
            raise

        print("[MESSAGE HANDLER] 訊息處理完成")

    except Exception as e:
        print(f"[MESSAGE HANDLER] 訊息處理失敗: {str(e)}")
        print(f"[MESSAGE HANDLER] 完整錯誤追蹤: {traceback.format_exc()}")

        # Try to send error message
        try:
            error_message = TextMessage(text="處理請求時發生錯誤，請稍後再試")
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[error_message]
            )
            line_bot_api.reply_message(reply_request)
        except Exception as send_error:
            print(f"[MESSAGE HANDLER] 發送錯誤訊息也失敗: {send_error}")

        raise

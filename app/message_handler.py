import os
import traceback
from pydantic import HttpUrl, ValidationError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ImageMessage, ApiException
)
from dotenv import load_dotenv

from .database import get_prisma_client
from .url_shortener import create_short_url

load_dotenv()

# LINE Bot API client
CHANNEL_TOKEN = os.getenv("CHANNEL_TOKEN")

print(f"[DEBUG] CHANNEL_TOKEN length: {len(CHANNEL_TOKEN) if CHANNEL_TOKEN else 'None'}")
print(
    f"[DEBUG] CHANNEL_TOKEN preview: {CHANNEL_TOKEN[:20]}..."
    if CHANNEL_TOKEN else "No CHANNEL_TOKEN"
)

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

    reply_messages = []

    try:
        # Validate URL format using Pydantic
        try:
            print("[MESSAGE HANDLER] 開始驗證 URL 格式...")
            validated_url = HttpUrl(message_text)
            print(f"[MESSAGE HANDLER] URL 驗證成功: {validated_url}")

            # Create short URL using internal logic
            print("[MESSAGE HANDLER] 開始生成短網址...")
            db = await get_prisma_client()
            result = await create_short_url(db, str(validated_url))
            print(f"[MESSAGE HANDLER] 短網址生成結果: {result}")

            short_url = result.get("shortUrl")
            short_code = result.get("shortCode")
            
            if short_url and short_code:
                # Create QR code image URL - using the service's own domain
                base_url = os.getenv("BASE_URL", "https://s8l-linebot.zeabur.app")
                qr_image_url = f"{base_url}/qr/{short_code}"
                
                # Create text message with short URL info
                text_message = TextMessage(
                    text=f"🔗 短網址已生成：\n{short_url}\n\n📱 掃描下方 QR Code 也可直接開啟連結"
                )
                
                # Create image message with QR code
                image_message = ImageMessage(
                    original_content_url=qr_image_url,
                    preview_image_url=qr_image_url
                )
                
                # Reply with both messages
                reply_messages = [text_message, image_message]
                print(f"[MESSAGE HANDLER] 成功生成短網址: {short_url}")
                print(f"[MESSAGE HANDLER] QR Code 圖片 URL: {qr_image_url}")
            else:
                reply_messages = [TextMessage(text="短網址產生失敗，請稍後再試")]
                print("[MESSAGE HANDLER] 短網址生成失敗")

        except ValidationError as e:
            print(f"[MESSAGE HANDLER] URL 格式驗證失敗: {e}")

            # Check for common greetings
            greetings = ["你好", "hi", "hello", "嗨", "安安", "哈囉", "早安", "午安", "晚安"]
            help_commands = ["help", "幫助", "說明", "指令"]

            if message_text.lower() in greetings:
                reply_messages = [TextMessage(
                    text=(
                        "你好！歡迎使用短網址服務 📎\n\n"
                        "直接傳送網址給我，我會幫您生成短網址和 QR Code！\n\n"
                        "範例：\nhttps://www.google.com"
                    )
                )]
            elif message_text.lower() in help_commands:
                reply_messages = [TextMessage(
                    text=(
                        "📎 短網址服務使用說明\n\n"
                        "直接傳送完整網址給我即可：\n"
                        "• 支援 http:// 或 https:// 開頭\n"
                        "• 例如：https://www.example.com\n\n"
                        "我會立即為您生成短網址和 QR Code！"
                    )
                )]
            else:
                reply_messages = [TextMessage(
                    text=(
                        "請提供有效的網址格式 (http:// 或 https://)\n\n"
                        "範例：https://www.google.com"
                    )
                )]

        except ValueError as e:
            print(f"[MESSAGE HANDLER] 值錯誤: {e}")
            reply_messages = [TextMessage(text=str(e))]

        except (ConnectionError, TimeoutError) as e:
            print(f"[MESSAGE HANDLER] 網路連接錯誤: {e}")
            print(f"[MESSAGE HANDLER] 錯誤詳情: {traceback.format_exc()}")
            reply_messages = [TextMessage(text="網路連接錯誤，請稍後再試")]
        except Exception as e:
            print(f"[MESSAGE HANDLER] 生成短網址時發生錯誤: {e}")
            print(f"[MESSAGE HANDLER] 錯誤詳情: {traceback.format_exc()}")
            reply_messages = [TextMessage(text="短網址服務暫時無法使用，請稍後再試")]

        # Send reply via LINE
        print("[MESSAGE HANDLER] 準備發送回覆訊息...")
        for i, msg in enumerate(reply_messages):
            if hasattr(msg, 'text'):
                print(f"[MESSAGE HANDLER] 回覆訊息 {i+1}: {msg.text}")
            else:
                print(f"[MESSAGE HANDLER] 回覆訊息 {i+1}: 圖片訊息")

        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=reply_messages
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
        except (ApiException, ConnectionError) as send_error:
            print(f"[MESSAGE HANDLER] 發送錯誤訊息失敗: {send_error}")
        except Exception as send_error:
            print(f"[MESSAGE HANDLER] 發送錯誤訊息時發生未知錯誤: {send_error}")

        raise

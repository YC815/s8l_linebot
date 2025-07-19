import os
import hashlib
import hmac
import base64
from typing import List

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError
from prisma import Prisma
from pydantic import BaseModel
from dotenv import load_dotenv

from .message_handler import process_message_sync
from .database import get_db, get_prisma_client, disconnect_prisma
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

# Initialize Prisma client on startup
@app.on_event("startup")
async def startup():
    await get_prisma_client()

@app.on_event("shutdown")
async def shutdown():
    await disconnect_prisma()

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
async def webhook(request: Request):
    """Handle LINE webhook events"""
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    
    print(f"[WEBHOOK] Received request from {request.client.host if request.client else 'unknown'}")
    print(f"[WEBHOOK] Signature: {signature[:20]}..." if signature else "[WEBHOOK] No signature")
    print(f"[WEBHOOK] Body length: {len(body)}")
    
    # Check if body is empty
    if not body:
        print("[WEBHOOK] Error: Empty request body")
        raise HTTPException(status_code=400, detail="Empty request body")
    
    # Check if signature exists
    if not signature:
        print("[WEBHOOK] Error: Missing X-Line-Signature header")
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")
    
    # Verify signature
    try:
        print(f"[WEBHOOK] Channel Secret length: {len(CHANNEL_SECRET) if CHANNEL_SECRET else 'None'}")
        print(f"[WEBHOOK] Channel Secret preview: {CHANNEL_SECRET[:10]}..." if CHANNEL_SECRET else "No Channel Secret")
        
        if not verify_signature(body, signature):
            print("[WEBHOOK] Error: Invalid signature")
            raise HTTPException(status_code=400, detail="Invalid signature")
        print("[WEBHOOK] Signature verification passed")
    except Exception as e:
        print(f"[WEBHOOK] Error verifying signature: {e}")
        raise HTTPException(status_code=400, detail="Signature verification failed")
    
    # Parse events
    try:
        events = webhook_handler.parser.parse(body.decode('utf-8'), signature)
        print(f"[WEBHOOK] Successfully parsed {len(events)} events")
    except InvalidSignatureError as e:
        print(f"[WEBHOOK] Invalid signature error: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"[WEBHOOK] Error parsing events: {e}")
        raise HTTPException(status_code=400, detail="Event parsing failed")
    
    # Process events in background
    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            print(f"[LINE MESSAGE] User: {event.source.user_id}, Message: {event.message.text}")
            print(f"[LINE MESSAGE] Reply Token: {event.reply_token}")
            
            # Process message synchronously
            print(f"[WEBHOOK] 正在處理訊息...")
            try:
                await process_message_sync(event.reply_token, event.message.text)
                print(f"[WEBHOOK] 訊息處理完成")
            except Exception as e:
                print(f"[WEBHOOK] 處理訊息失敗: {e}")
                import traceback
                print(f"[WEBHOOK] 錯誤追蹤: {traceback.format_exc()}")
        else:
            print(f"[WEBHOOK] Ignoring event type: {type(event)}")
    
    return JSONResponse(content={"status": "ok"})

@app.get("/")
async def home():
    """Home page with service status"""
    from datetime import datetime
    
    # Check database connection
    try:
        db = await get_prisma_client()
        await db.user.count()  # Simple query to test connection
        db_status = "✅ 已連接"
    except Exception as e:
        db_status = f"❌ 連接失敗: {str(e)}"
    
    # Check Redis connection
    try:
        from redis import Redis
        redis_client = Redis.from_url(os.getenv("BROKER_URL", "redis://localhost:6379/0"))
        redis_client.ping()
        redis_status = "✅ 已連接"
    except Exception as e:
        redis_status = f"❌ 連接失敗: {str(e)}"
    
    # Basic service info
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LINE 短網址服務 - 服務狀態</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; text-align: center; }}
            .status {{ padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .healthy {{ background-color: #d4edda; border: 1px solid #c3e6cb; }}
            .unhealthy {{ background-color: #f8d7da; border: 1px solid #f5c6cb; }}
            .info {{ background-color: #d1ecf1; border: 1px solid #bee5eb; }}
            .api-endpoints {{ margin-top: 20px; }}
            .endpoint {{ background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 5px; }}
            .time {{ text-align: center; color: #666; margin-top: 20px; }}
            .footer {{ text-align: center; margin-top: 30px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 LINE 短網址服務</h1>
            
            <div class="status info">
                <strong>📊 服務狀態概覽</strong><br>
                伺服器正在運行中
            </div>
            
            <div class="status {'healthy' if '✅' in db_status else 'unhealthy'}">
                <strong>🗄️ 資料庫狀態:</strong> {db_status}
            </div>
            
            <div class="status {'healthy' if '✅' in redis_status else 'unhealthy'}">
                <strong>🔄 Redis 狀態:</strong> {redis_status}
            </div>
            
            <div class="api-endpoints">
                <h3>📡 API 端點</h3>
                <div class="endpoint">
                    <strong>POST /api/shorten</strong> - 創建短網址<br>
                    <small>範例: curl -X POST -H "Content-Type: application/json" -d '{{"url":"https://github.com"}}' /api/shorten</small>
                </div>
                <div class="endpoint">
                    <strong>GET /{{short_code}}</strong> - 短網址重定向<br>
                    <small>範例: /{"{short_code}"} → 自動重定向到原始網址</small>
                </div>
                <div class="endpoint">
                    <strong>POST /webhook</strong> - LINE Bot Webhook 接收器<br>
                    <small>用於接收 LINE 平台的訊息事件</small>
                </div>
                <div class="endpoint">
                    <strong>GET /health</strong> - 健康檢查<br>
                    <small>返回簡單的健康狀態 JSON</small>
                </div>
            </div>
            
            <div class="time">
                📅 檢查時間: {current_time}
            </div>
            
            <div class="footer">
                <p>💡 此服務提供 LINE Bot 短網址功能</p>
                <p>🔗 發送網址給 LINE Bot，即可獲得短網址</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/api/shorten", response_model=ShortenResponse)
async def shorten_url(request: ShortenRequest, db: Prisma = Depends(get_db)):
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
async def redirect_url(short_code: str, db: Prisma = Depends(get_db)):
    """Redirect to original URL"""
    original_url = await get_original_url(db, short_code)
    if original_url:
        return RedirectResponse(url=original_url, status_code=302)
    else:
        raise HTTPException(status_code=404, detail="短網址不存在")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
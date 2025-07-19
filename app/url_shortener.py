"""URL shortener module with Prisma Client Python."""
import random
import re
import asyncio
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup
from prisma import Prisma
from prisma.models import User

# URL-safe characters for short code generation
URL_SAFE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'

def generate_short_code(length: int = 6) -> str:
    """Generate a random short code using URL-safe characters"""
    return ''.join(random.choices(URL_SAFE_CHARS, k=length))

def validate_url(url: str) -> str:
    """Validate and normalize URL, automatically adding https:// if needed"""
    url = url.strip()
    
    # Add https:// if no protocol is specified
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Validate URL format
    try:
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            raise ValueError("網址格式錯誤，請檢查")
        return url
    except Exception:
        raise ValueError("網址格式錯誤，請檢查")

async def fetch_page_title(url: str) -> str:
    """Fetch page title from URL with timeout and error handling"""
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; URL-Shortener/1.0)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        }
        
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return "無法獲取標題"
                
                # Only read first 64KB to avoid large files
                content = await response.read()
                if len(content) > 64 * 1024:
                    content = content[:64 * 1024]
                
                # Parse HTML and extract title
                soup = BeautifulSoup(content, 'html.parser')
                title_tag = soup.find('title')
                
                if title_tag and title_tag.text:
                    title = title_tag.text.strip()
                    # Clean up title
                    title = re.sub(r'\s+', ' ', title)
                    return title[:200]  # Limit to 200 characters
                
                return "無法獲取標題"
                
    except asyncio.TimeoutError:
        return "無法獲取標題"
    except Exception as e:
        print(f"Error fetching title for {url}: {e}")
        return "無法獲取標題"

async def get_or_create_linebot_user(db: Prisma) -> User:
    """Get or create a dedicated LINE Bot user for URL attribution"""
    linebot_email = "linebot@s8l.xyz"
    
    # Try to find existing LINE Bot user
    user = await db.user.find_unique(where={"email": linebot_email})
    
    if user:
        return user
    
    # Create LINE Bot user if not exists
    user = await db.user.create(
        data={
            "email": linebot_email,
            "password": "linebot_system_user",  # System user, password not used
            "name": "LINE Bot System",
            "emailVerified": True
        }
    )
    
    return user

async def create_short_url(db: Prisma, original_url: str) -> Dict[str, Any]:
    """Create a short URL, handling duplicates and collisions"""
    
    # Validate URL
    validated_url = validate_url(original_url)
    
    # Check for recursive shortening (prevent our own domain)
    try:
        parsed = urlparse(validated_url)
        if parsed.hostname in ['s8l.xyz', 'www.s8l.xyz', 'localhost', '127.0.0.1']:
            raise ValueError("不能縮短本服務的網址")
    except Exception:
        pass
    
    # Get or create LINE Bot user
    linebot_user = await get_or_create_linebot_user(db)
    
    # Check if URL already exists
    existing_url = await db.url.find_unique(where={"originalUrl": validated_url})
    
    if existing_url:
        # Check if this user already has this URL
        existing_user_url = await db.userurl.find_first(
            where={
                "userId": linebot_user.id,
                "urlId": existing_url.id,
                "customDomainId": None  # Only for basic short URLs
            }
        )
        
        # Create UserUrl association if not exists
        if not existing_user_url:
            await db.userurl.create(
                data={
                    "userId": linebot_user.id,
                    "urlId": existing_url.id
                }
            )
        
        return {
            "shortCode": existing_url.shortCode,
            "originalUrl": existing_url.originalUrl,
            "title": existing_url.title,
            "shortUrl": f"https://s8l.xyz/{existing_url.shortCode}"
        }
    
    # Generate unique short code with collision detection
    max_attempts = 10
    short_code = None
    
    for attempt in range(max_attempts):
        potential_code = generate_short_code()
        
        # Check if short code already exists
        existing = await db.url.find_unique(where={"shortCode": potential_code})
        if not existing:
            short_code = potential_code
            break
        
        if attempt == max_attempts - 1:
            raise ValueError("生成短網址失敗，請重試")
    
    # Fetch page title asynchronously
    title = await fetch_page_title(validated_url)
    
    # Create new URL record
    new_url = await db.url.create(
        data={
            "originalUrl": validated_url,
            "shortCode": short_code,
            "title": title
        }
    )
    
    # Create UserUrl association
    await db.userurl.create(
        data={
            "userId": linebot_user.id,
            "urlId": new_url.id
        }
    )
    
    return {
        "shortCode": new_url.shortCode,
        "originalUrl": new_url.originalUrl,
        "title": new_url.title,
        "shortUrl": f"https://s8l.xyz/{new_url.shortCode}"
    }

async def get_original_url(db: Prisma, short_code: str) -> Optional[str]:
    """Get original URL by short code and increment click count"""
    url_record = await db.url.find_unique(where={"shortCode": short_code})
    
    if url_record:
        # Increment click count
        await db.url.update(
            where={"id": url_record.id},
            data={"clickCount": {"increment": 1}}
        )
        return url_record.originalUrl

    return None
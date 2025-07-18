import random
import string
import re
import asyncio
import uuid
from typing import Optional
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import aiohttp
from bs4 import BeautifulSoup
from .models import Url

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

async def create_short_url(db: AsyncSession, original_url: str) -> dict:
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
    
    # Check if URL already exists
    result = await db.execute(
        select(Url).where(Url.original_url == validated_url)
    )
    existing_url = result.scalar_one_or_none()
    
    if existing_url:
        return {
            "shortCode": existing_url.short_code,
            "originalUrl": existing_url.original_url,
            "title": existing_url.title,
            "shortUrl": f"https://s8l.xyz/{existing_url.short_code}"
        }
    
    # Generate unique short code with collision detection
    max_attempts = 10
    for attempt in range(max_attempts):
        short_code = generate_short_code()
        
        # Check if short code already exists
        result = await db.execute(
            select(Url).where(Url.short_code == short_code)
        )
        if result.scalar_one_or_none() is None:
            break
        
        if attempt == max_attempts - 1:
            raise ValueError("生成短網址失敗，請重試")
    
    # Fetch page title asynchronously
    title = await fetch_page_title(validated_url)
    
    # Create new URL record
    new_url = Url(
        id=str(uuid.uuid4()),
        original_url=validated_url,
        short_code=short_code,
        title=title
    )
    
    try:
        db.add(new_url)
        await db.commit()
        await db.refresh(new_url)
        
        return {
            "shortCode": new_url.short_code,
            "originalUrl": new_url.original_url,
            "title": new_url.title,
            "shortUrl": f"https://s8l.xyz/{new_url.short_code}"
        }
    except IntegrityError:
        await db.rollback()
        raise ValueError("短網址生成失敗，請重試")

async def get_original_url(db: AsyncSession, short_code: str) -> Optional[str]:
    """Get original URL by short code and increment click count"""
    result = await db.execute(
        select(Url).where(Url.short_code == short_code)
    )
    url_record = result.scalar_one_or_none()
    
    if url_record:
        # Increment click count
        url_record.click_count += 1
        await db.commit()
        return url_record.original_url
    
    return None
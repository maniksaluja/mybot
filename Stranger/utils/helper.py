import asyncio
import uuid
import re
import os
import random
import string
import time
import requests
from functools import lru_cache
from typing import Dict, Tuple, Optional
from datetime import datetime as dt

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked
from ..logger import LOGGER
from cryptography.fernet import Fernet

from Stranger.utils.database import get_token_subscription

SECRET_KEY = Fernet.generate_key()
cipher_suite = Fernet(SECRET_KEY)

def thumb_link(file) -> Optional[str]:
    """
    Upload file to imgbb.com and return the thumbnail URL
    
    Args:
        file: File object (bytes-like, BytesIO, file path, or bytes) to upload
    
    Returns:
        str: Thumbnail URL if successful, None if failed
    """
    try:
        file_content = None
        
        if isinstance(file, (str, bytes)):
            if isinstance(file, str):
                with open(file, 'rb') as f:
                    file_content = f.read()
            else:
                file_content = file
        elif hasattr(file, 'getvalue'):
            file_content = file.getvalue()
        elif hasattr(file, 'read'):
            current_pos = file.tell() if hasattr(file, 'tell') else None
            if current_pos is not None:
                file.seek(0) 
            file_content = file.read()
            if current_pos is not None:
                file.seek(current_pos)  
        else:
            return None

        if not file_content or len(file_content) == 0:
            return None
        
        if len(file_content) > 32 * 1024 * 1024:
            return None
        import base64
        base64_image = base64.b64encode(file_content).decode('utf-8')

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        data = {
            'key': '67bb31576b8941b9aa1cc0239dde0a39',
            'image': base64_image,
        }

        response = requests.post('https://api.imgbb.com/1/upload', headers=headers, data=data, timeout=30)

        if response.status_code == 200:
            try:
                json_response = response.json()
                
                if (json_response.get('success') or json_response.get('status') == 200) and 'data' in json_response:
                    image_data = json_response['data']
                    display_url = image_data.get('display_url')
                    if display_url:
                        return display_url
                    else:
                        return image_data.get('url')
                else:
                    error_info = json_response.get('error', {})
                    status_code = json_response.get('status_code', json_response.get('status', 'Unknown'))
                    LOGGER(__name__).error(f"Upload failed - Status: {status_code}, Error: {error_info}")
                    LOGGER(__name__).error(f"Full response: {json_response}")
                    return None
            except ValueError as e:
                LOGGER(__name__).error(f"Invalid JSON response: {e}, Response text: {response.text[:500]}")
                return None
        else:
            LOGGER(__name__).error(f"HTTP error: {response.status_code} - {response.reason}")
            LOGGER(__name__).error(f"Response text: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        LOGGER(__name__).error("Request timeout while uploading to imgbb")
        return None
    except requests.exceptions.RequestException as e:
        LOGGER(__name__).error(f"Request error while uploading to imgbb: {e}")
        return None
    except Exception as e:
        LOGGER(__name__).error(f"Unexpected error in thumb_link: {e}")
        import traceback
        LOGGER(__name__).error(f"Traceback: {traceback.format_exc()}")
        return None

def find_bot(bots:dict, username:str):
  for token, bot_info in bots.items():
    if 'username' in bot_info and bot_info['username'] == username:
      return bot_info
  return None

MAX_RETRIES = 3

async def retry_with_flood_wait(func, *args, **kwargs):
    """Retry function with FloodWait handling"""
    for _ in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except FloodWait as fw:
            await asyncio.sleep(int(fw.value))
        except UserIsBlocked:
            break
        except Exception as e:
            LOGGER(__name__).error(f"Error in retry_with_flood_wait: inputs: {func}, error: {e}")
            raise
    raise Exception("Max retries exceeded")

def generate_unique_file_id(length=16):
    try:
        result = ''
        while len(result) < length:
            uuid_str = str(uuid.uuid4().hex).upper()
            letters = ''.join(c for c in uuid_str if c.isalpha())
            result += letters
        return result[:length]
    except Exception as e:
        raise RuntimeError(f"Failed to generate unique ID: {str(e)}")

async def get_messages(client:Client, message_ids):
    messages = []
    total_messages = 0
    while total_messages != len(message_ids):
        temb_ids = message_ids[total_messages:total_messages+200]
        try:
            msgs = await client.get_messages(
                chat_id=client.db_channel,
                message_ids=temb_ids
            )
        except FloodWait as e:
            await asyncio.sleep(e.x)
            msgs = await client.get_messages(
                chat_id=client.db_channel,
                message_ids=temb_ids
            )
        except:
            pass
        total_messages += len(temb_ids)
        messages.extend(msgs)
    return messages

async def get_message_id(client:Client, message:Message) -> int:
    if message.forward_from_chat:
        if message.forward_from_chat.id == client.db_channel:
            return message.forward_from_message_id
        else:
            return 0
    elif message.forward_sender_name:
        return 0
    elif message.text:
        pattern = r"https://t.me/(?:c/)?(.*)/(\d+)"
        matches = re.match(pattern, message.text)
        if not matches:
            return 0
        channel_id = matches.group(1)
        msg_id = int(matches.group(2))
        if channel_id.isdigit():
            if f"-100{channel_id}" == str(client.db_channel):
                return msg_id
        else:
            if channel_id == client.db_channel:
                return msg_id
    else:
        return 0

def get_exp_time(seconds):
    periods = [('days', 86400), ('hours', 3600), ('mins', 60), ('secs', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result

def get_readable_time(seconds: int) -> str:
    if seconds == 0:
        return "0s"

    days, remainder = divmod(float(seconds), 86400)  # 24*60*60
    hours, remainder = divmod(remainder, 3600)  # 60*60
    minutes, remainder = divmod(remainder, 60)
    seconds = round(remainder)  # Round seconds to nearest integer
    
    time_parts = []
    if int(days) > 0:
        time_parts.append(f"{int(days)}Days")
    if int(hours) > 0:
        time_parts.append(f"{int(hours)}h")
    if int(minutes) > 0:
        time_parts.append(f"{int(minutes)}m")
    if seconds > 0:
        time_parts.append(f"{seconds}s")
        
    return " ".join(time_parts)


def get_approximate_time(seconds: int) -> str:
    seconds = round(seconds)

    if seconds < 60:
        return f"{seconds}S"
    
    elif seconds < 3600:  # Less than 1 hour
        minutes = round(seconds / 60)
        return f"{minutes}M"
    
    else:  # Greater than or equal to 1 hour
        hours = round(seconds / 3600)
        return f"{hours}H"

def extract_file_id_from_text(text):
    """
    Extract file ID from a message text containing a Telegram bot link
    
    """
    if not text:
        return None
    
    # Look for patterns with different Telegram domain formats
    patterns = [
        r't\.me/[^?]+\?start=([A-Z0-9]+)',
        r'telegram\.me/[^?]+\?start=([A-Z0-9]+)',
        r'\?start=([A-Z0-9]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            content_id = match.group(1)
            if content_id.lower().startswith('promo_'):
                content_id = content_id[6:] 
            return content_id
    
    return None

async def generate_unique_token():
    token_length = 16
    while True:
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        uuid_part = str(uuid.uuid4())[:8]
        token = f"{random_part}{uuid_part}"[:token_length]
        if not await get_token_subscription(token):
            return token

def get_media_data(message:Message) -> Optional[Dict[str, str]]:
    media_data = None
    
    if message.photo:
        media_data = {
            "type": "photo",
            "file_id": message.photo.file_id,
            "caption": message.caption or "",
            "thumbnail": message.photo.thumbs[-1].file_id if message.photo.thumbs else None
        }
    elif message.video:
        media_data = {
            "type": "video",
            "file_id": message.video.file_id,
            "caption": message.caption or "",
            "thumbnail": message.video.thumbs[-1].file_id if message.video.thumbs else None
        }
    elif message.document:
        media_data = {
            "type": "document",
            "file_id": message.document.file_id,
            "caption": message.caption or "",
            "thumbnail": message.document.thumbs[-1].file_id if message.document.thumbs else None
        }
    elif message.audio:
        media_data = {
            "type": "audio",
            "file_id": message.audio.file_id,
            "caption": message.caption or "",
            "thumbnail": message.audio.thumbs[-1].file_id if message.audio.thumbs else None
        }
    elif message.voice:
        media_data = {
            "type": "voice",
            "file_id": message.voice.file_id,
            "caption": message.caption or "",
        }
    elif message.video_note:
        media_data = {
            "type": "video_note",
            "file_id": message.video_note.file_id,
            "caption": message.caption or "",
            "thumbnail":message.video_note.thumbs[-1].file_id if message.video_note.thumbs else None
        }
    elif message.sticker:
        media_data = {
            "type": "sticker",
            "file_id": message.sticker.file_id,
            "caption": message.caption or "",
            "thumbnail":message.sticker.thumbs[-1].file_id if message.sticker.thumbs else None
        }
    elif message.animation:
        media_data = {
            "type": "animation",
            "file_id": message.animation.file_id,
            "caption": message.caption or "",
            "thumbnail": message.animation.thumbs[-1].file_id if message.animation.thumbs else None
        }   
    # elif message.text:
    #     media_data = {
    #         "type": "text",
    #         "text": message.text,
    #     }
    
    return media_data

#Screenshot---------------------------------------------------------------------------------------------------------------

def hhmmss(seconds):
    x = time.strftime('%H:%M:%S', time.gmtime(seconds))
    return x

async def screenshot(video, duration, output_dir="data/files/temp"):
    """
    Create a thumbnail screenshot from video at middle timestamp
    
    Args:
        video: Path to video file
        duration: Video duration in seconds
        output_dir: Directory to save screenshot
    
    Returns:
        str: Path to screenshot file or None if failed
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Calculate timestamp (middle of video)
        time_stamp = hhmmss(int(duration) / 2)
        
        # Generate unique output filename
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(output_dir, f"thumb_{timestamp}.jpg")
        
        # FFmpeg command to extract frame
        cmd = [
            "ffmpeg",
            "-ss", f"{time_stamp}",  # Seek to timestamp
            "-i", f"{video}",        # Input video
            "-frames:v", "1",        # Extract 1 frame
            "-q:v", "2",            # High quality
            "-vf", "scale=320:240",  # Resize for thumbnail
            f"{out}",               # Output file
            "-y"                    # Overwrite if exists
        ]
        
        # Execute FFmpeg command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Check if file was created successfully
        if os.path.isfile(out) and os.path.getsize(out) > 0:
            LOGGER(__name__).info(f"Screenshot created: {out}")
            return out
        else:
            LOGGER(__name__).error(f"Failed to create screenshot. FFmpeg stderr: {stderr.decode()}")
            return None
            
    except Exception as e:
        LOGGER(__name__).error(f"Error creating screenshot: {e}")
        return None

async def create_video_thumbnail(video_path: str, duration: int) -> Optional[str]:
    """
    Wrapper function to create video thumbnail with better error handling
    
    Args:
        video_path: Path to video file
        duration: Video duration in seconds
    
    Returns:
        str: Path to thumbnail file or None if failed
    """
    try:
        if not os.path.isfile(video_path):
            return None
        
        thumb = await screenshot(video_path, duration)
        
        if thumb:
            return thumb
        
        # Check if FFmpeg is available
        try:
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            if process.returncode != 0:
                LOGGER(__name__).error("FFmpeg not available")
                return None
        except FileNotFoundError:
            LOGGER(__name__).error("FFmpeg not installed")
            return None
        
        
    except Exception as e:
        LOGGER(__name__).error(f"Error in create_video_thumbnail: {e}")
        return None


from typing import Union, Optional, Dict
import asyncio
import time
import pytz
import datetime

from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, MessageIdInvalid, FloodWait
from Stranger import app, LOGGER
from Stranger.utils.database import (
    save_daily_reaction_post,
    get_daily_reaction_post,
    update_daily_reaction_post_activity,
    get_active_daily_reaction_posts,
    get_daily_reaction_aggregates,
    get_category_post_counts
)
from config import BASE_GIF, REACTION_CHANNEL, emoji

def get_today_date_str() -> str:
    """Get today's date string in IST timezone"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist).strftime('%Y_%m_%d')

def get_previous_date_str() -> str:
    """Get previous day's date string in IST timezone"""
    ist = pytz.timezone('Asia/Kolkata')
    yesterday = datetime.datetime.now(ist) - datetime.timedelta(days=1)
    return yesterday.strftime('%Y_%m_%d')

def format_date_for_button(date_str: str) -> str:
    """Format date string for button display"""
    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y_%m_%d')
        return date_obj.strftime('%B•%d•%Y')
    except:
        return date_str

async def update_previous_post_button(date_str: str) -> bool:
    """Update previous post's button to show the date instead of 'Get Fresh Content'"""
    try:
        # Get post from database
        post_info = await get_daily_reaction_post(date_str)
        
        if not post_info or not post_info['is_active']:
            LOGGER(__name__).debug(f"No active post found for {date_str}")
            return False

        if not post_info["message_id"]:
            LOGGER(__name__).debug(f"No message_id found for {date_str}")
            return False

        # Get current message
        try:
            current_msg = await app.get_messages(
                chat_id=post_info["chat_id"],
                message_ids=post_info["message_id"]
            )
        except Exception as e:
            LOGGER(__name__).warning(f"Cannot get existing message for {date_str}: {e}")
            return False

        # Format date for button
        formatted_date = format_date_for_button(date_str)
        
        # Create updated button with date
        btn = [
            [
                InlineKeyboardButton(
                    text=f"📅 {formatted_date}", 
                    url=f"https://t.me/{app.username}?start=latest_{date_str}"
                ),
            ]
        ]
        
        try:
            await current_msg.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
            )
            
            return True
            
        except MessageNotModified:
            LOGGER(__name__).debug(f"Button already updated for {date_str}")
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Failed to update button for {date_str}: {e}")
            return False
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to update previous post button for {date_str}: {e}")
        return False

daily_posts: Dict[str, Dict] = {}
update_pending = False

async def create_daily_reaction_post(date_str: str = None) -> Optional[Message]:
    """Create a new daily reaction post for specific date"""
    if not date_str:
        date_str = get_today_date_str()
    global daily_posts
    try:
        # Get content counts for the date (use new system)
        post_counts = await get_category_post_counts(date_str)
        
        # Generate post content
        message_content = await generate_reaction_post_content(post_counts, date_str)
        
        # Create inline keyboard
        btn = [
            [
                InlineKeyboardButton(
                    text="𝖦𝖾𝗍 𝖥𝗋𝖾𝗌𝗁 𝖢𝗈𝗇𝗍𝖾𝗇𝗍 ", 
                    url=f"https://t.me/{app.username}?start=latest_{date_str}"
                ),
            ]
        ]
        
        # Send the post
        msg = await app.send_video(
            chat_id=REACTION_CHANNEL, 
            video=BASE_GIF,
            caption=message_content, 
            parse_mode=ParseMode.DEFAULT, 
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
        # Save to database
        await save_daily_reaction_post(
            date_str=date_str,
            message_id=msg.id,
            chat_id=msg.chat.id,
            is_active=True
        )
        
        # Cache the post
        daily_posts[date_str] = {
            "message": msg,
            "last_updated": datetime.datetime.now()
        }
        
        LOGGER(__name__).info(f"Created daily reaction post for {date_str}")
        return msg
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to create daily reaction post for {date_str}: {e}")
        return None

async def update_daily_reaction_post(date_str: str = None) -> bool:
    """Update existing daily reaction post"""
    if not date_str:
        date_str = get_today_date_str()
    global daily_posts
    try:
        post = daily_posts.get(date_str)
        if post:
            current_msg = post['message'] 
        else:
            # Get post from database
            post_info = await get_daily_reaction_post(date_str)

            if not post_info or not post_info['is_active']:
                return

            if not post_info["message_id"]:
                LOGGER(__name__).info(f"No existing post found for {date_str}, creating new one")
                msg = await create_daily_reaction_post(date_str, force=True)
                return msg is not None

            # Get current message
            try:
                current_msg = await app.get_messages(
                    chat_id=post_info["chat_id"],
                    message_ids=post_info["message_id"]
                )
            except Exception as e:
                LOGGER(__name__).warning(f"Cannot get existing message for {date_str}: {e}")
                # Create new post if old one is not accessible
                msg = await create_daily_reaction_post(date_str, force=True)
                return msg is not None
        
        post_counts = await get_category_post_counts(date_str)
        message_content = await generate_reaction_post_content(post_counts, date_str)
        
        # Update the message - check if it's today's post or older post
        today_date = get_today_date_str()
        if date_str == today_date:
            # Today's post gets "Get Fresh Content" button
            button_text = "𝖦𝖾𝗍 𝖥𝗋𝖾𝗌𝗁 𝖢𝗈𝗇𝗍𝖾𝗇𝗍 "
        else:
            # Previous posts get date button
            formatted_date = format_date_for_button(date_str)
            button_text = f"📅 {formatted_date}"
        
        btn = [
            [
                InlineKeyboardButton(
                    text=button_text, 
                    url=f"https://t.me/{app.username}?start=latest_{date_str}"
                ),
            ]
        ]
        try:
            await current_msg.edit_caption(
                message_content, 
                parse_mode=ParseMode.DEFAULT,
                reply_markup=InlineKeyboardMarkup(btn)
            )
            
            # Update database
            await save_daily_reaction_post(
                date_str=date_str,
                message_id=current_msg.id,
                chat_id=current_msg.chat.id,
                is_active=True
            )
            
            LOGGER(__name__).info(f"Updated daily reaction post for {date_str}")
            return True
            
        except MessageNotModified:
            LOGGER(__name__).debug(f"No changes needed for {date_str}")
            return True
        except FloodWait as e:
            LOGGER(__name__).warning(f"FloodWait for {date_str}: {e.value}s")
            asyncio.create_task(retry_update_after_flood(date_str, e.value))
            return False
        except Exception as e:
            LOGGER(__name__).error(f"Failed to update message for {date_str}: {e}")
            return False
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to update daily reaction post for {date_str}: {e}")
        return False

async def retry_update_after_flood(date_str: str, wait_time: int):
    """Retry update after FloodWait"""
    await asyncio.sleep(wait_time + 1)
    await update_daily_reaction_post(date_str)

async def generate_reaction_post_content(post_counts: dict = None, date_str: str = None):
    """Generate content for reaction post with enhanced formatting"""
    if not date_str:
        date_str = get_today_date_str()
    
    if not post_counts:
        post_counts = await get_category_post_counts(date_str)
    
    
    message = f"**ShanayaFANBaseBot Has Been Updated With Fresh Content.!!! **\n\n"

    category_display = {
        'indian': 'Indian',
        'global': 'Global', 
        'dark': 'Dark',
        'others': 'Others'
    }

    total_posts = 0
    for category, display_name in category_display.items():
        count = post_counts.get(category, 0)
        total_posts += count
        message += f"**• {display_name} 𝘊𝘰𝘯𝘵𝘦𝘯𝘵▾ **\n"
        message += f">** {count:02d} 𝘓𝘪𝘯𝘬𝘴 𝘗𝘰𝘀𝘵𝘦𝘥 **\n"
    
    message += f"\n**📊 Total: {total_posts} Links Posted**\n\n"

    reactions_data = await get_daily_reaction_aggregates(date_str)
    total_emojis = len([k for k in emoji.keys() if k.startswith('emoji_')])
    
    reaction_section = f"**𝖳𝗈𝖽𝖺𝗒'𝗌 𝖢𝗈𝗇𝗍𝖾𝗇𝗍 𝖥𝖾𝖾𝖽𝖡𝖺𝖼𝗄𝗌**\n"
    for i in range(0, total_emojis, 4):
        row = format_reaction_row(range(total_emojis), reactions_data, i)
        if row:
            reaction_section += f"{row}\n"
    
    message += reaction_section
    return message

def format_reaction_row(emoji_list, reactions, start_index):
    """Format a row of emoji reactions"""
    row = []
    for i in range(start_index, min(start_index + 4, len(emoji_list))):
        emoji_key = f"emoji_{i+1}"
        count = reactions.get(emoji_key, 0)
        row.append(f"{emoji[emoji_key]}**{count}**")
    return "<pre>" + " • ".join(row) + "• </pre>" if row else ""

async def restore_daily_reaction_posts():
    """Restore all active daily reaction posts on bot startup"""
    global daily_posts
    try:
        active_posts = await get_active_daily_reaction_posts()
        restored_count = 0
        
        for post_data in active_posts:
            date_str = post_data["date"]
            try:
                # Try to get the existing message
                msg = await app.get_messages(
                    chat_id=post_data["chat_id"],
                    message_ids=post_data["message_id"]
                )
                
                if msg and not msg.empty:
                    # Cache the restored post
                    daily_posts[date_str] = {
                        "message": msg,
                        "last_updated": post_data["last_updated"]
                    }
                    restored_count += 1
                else:
                    # Mark as inactive if message not found
                    await update_daily_reaction_post_activity(date_str, False)
                    LOGGER(__name__).warning(f"Post not found for {date_str}, marked as inactive")
            except Exception as e:
                LOGGER(__name__).warning(f"Error restoring post for {date_str}: {e}")
                await update_daily_reaction_post_activity(date_str, False)
        
        LOGGER(__name__).info(f"Restored {restored_count} daily reaction posts")
        return restored_count > 0
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to restore daily reaction posts: {e}")
        return False

async def trigger_reaction_post_update(force: bool = False, date_str:str = None):
    if date_str is None:
        date_str = get_today_date_str()
    global update_pending
    if update_pending and not force:
        return
    
    if force:
        update_pending = True
        await update_daily_reaction_post(date_str)
        update_pending = False
    
    update_pending = True
    await asyncio.sleep(120)
    await update_daily_reaction_post(date_str)
    update_pending = False

    return

async def create_today_reaction_post():
    """Create reaction post for today and update previous post button"""
    # Update previous post's button to show date
    previous_date = get_previous_date_str()
    await update_previous_post_button(previous_date)
    
    # Create today's post
    date_str = get_today_date_str()
    return await create_daily_reaction_post(date_str)

async def deactivate_old_posts(days_to_keep: int = 7):
    """Deactivate old reaction posts"""
    try:
        global daily_posts
        cutoff_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')) - datetime.timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime('%Y_%m_%d')
        
        # Get all active posts older than cutoff
        active_posts = await get_active_daily_reaction_posts()
        deactivated_count = 0
        
        for post_data in active_posts:
            if post_data["date"] < cutoff_str:
                await update_daily_reaction_post_activity(post_data["date"], False)
                # Remove from cache
                daily_posts.pop(post_data["date"], None)
                deactivated_count += 1
        
        LOGGER(__name__).info(f"Deactivated {deactivated_count} old reaction posts")
        return deactivated_count
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to deactivate old posts: {e}")
        return 0

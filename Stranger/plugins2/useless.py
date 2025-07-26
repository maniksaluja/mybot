
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from Stranger import app
from Stranger.misc import SUDOERS
from Stranger.utils.database import bot_users
from config import BANNED_USERS, USELESS_CHANNEL, WARNING_AUDIO
from time import time
from strings import MB_USELESS

# Constants

SPAM_WARNING = "Please don't spam"
MESSAGE_COOLDOWN = 10  # seconds
SPAM_BLOCK_TIME = 600  # 10 minutes

# Track user messages
user_messages = {}  # {user_id: {"count": 0, "last_time": timestamp, "warnings": 0, "blocked_until": 0}}
important_mode = {} # {user_id: {"active": bool,"del_message": Message, "messages": []}}

async def clear_important_mode(user_id: int) -> None:
    """Clear important mode for a user"""
    if user_id in important_mode:
        try:
            await important_mode[user_id]['del_message'].delete()
        except:
            pass
        del important_mode[user_id]    

@Client.on_message(filters.private & filters.incoming & ~SUDOERS & ~BANNED_USERS)
async def handle_useless(c: Client, msg: Message):
    user_id = msg.from_user.id
    current_time = time()

    if not await bot_users.is_user(app.helper_bot_username, user_id):
        await bot_users.add_user(app.helper_bot_username, user_id)

    if user_id in important_mode and important_mode[user_id]["active"]:
        if msg.text and msg.text.startswith("/"):
            del important_mode[user_id]
            return
        important_mode[user_id]["messages"].append(msg)
        return

    # Initialize user data if not exists 
    if user_id not in user_messages:
        user_messages[user_id] = {
            "count": 0,
            "last_time": current_time,
            "warnings": 0,
            "blocked_until": 0
        }

    user_data = user_messages[user_id]

    # Check if user is in timeout
    if user_data["blocked_until"] > current_time:
        return

    # Reset message count if more than 10 seconds passed
    if current_time - user_data["last_time"] > MESSAGE_COOLDOWN:
        user_data["count"] = 0
        user_data["last_time"] = current_time

    # Increment message count
    user_data["count"] += 1

    # Check for spam (10 messages in 10 seconds)
    if user_data["count"] >= 10:
        user_data["warnings"] += 1
        user_data["blocked_until"] = current_time + SPAM_BLOCK_TIME
        # Reset count
        user_data["count"] = 0
        
        # Handle warnings
        if user_data["warnings"] >= 3:
            user_data["warnings"] = 0  # Reset warnings
            user_data["blocked_until"] = current_time + 600
            await msg.reply_audio(
                audio=WARNING_AUDIO,
                caption=f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages, The Bot Will Ignore You For Next 5 Minutes.**",quote=True,disable_notification=True
            )
        else:
            await msg.reply_sticker("CAACAgUAAxkBAAENyjJnrucU5iUlWZjAaQAB7MCO5aVpwsgAAmkTAALatwhVlzot0t5jSDw2BA", disable_notification=True)
            await msg.reply(f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages, The Bot Will Ignore You For Next 5 Minutes.**",quote=True,disable_notification=True)
        return

    # Update last message time
    user_data["last_time"] = current_time

    await msg.reply(MB_USELESS.format(msg.from_user.mention),quote=True, disable_notification=False)

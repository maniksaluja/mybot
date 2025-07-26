import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from Stranger.utils.database.mongodatabase import get_content
from strings import ANNOUNCMENT_LINK, HOW_TO_USE_MAIN_BOT, UNWANTED_MESSAGES
from Stranger import app
from Stranger.misc import SUDOERS
from config import BANNED_USERS, IMPORTANT_AUDIO, USELESS_CHANNEL, START_IMG, WARNING_AUDIO

from time import time

# Constants
SPAM_WARNING = "Please don't spam"
MESSAGE_COOLDOWN = 10  # seconds
SPAM_BLOCK_TIME = 600  # 10 minutes

# Track user messages
user_messages = {}  # {user_id: {"count": 0, "last_time": timestamp, "warnings": 0, "blocked_until": 0}}
important_mode = {} # {user_id: {"active": bool, "messages": []}}

async def clear_important_mode(user_id: int) -> None:
    """Clear important mode for a user"""
    if user_id in important_mode:
        
        try:
            await important_mode[user_id]['del_message'].delete()
        except:
            pass

        del important_mode[user_id] 

pending_query = []

@app.on_message(
    filters.private 
    & filters.incoming 
    & ~SUDOERS 
    & ~BANNED_USERS
    & (
        (filters.regex(pattern=r"(?i)^(?!(TODAY'S CONTENT|INDIAN|GLOBAL|DARK|Buy Subscription|OTHERS)$)(?!\/).*"))
        | filters.media
    )
)
async def handle_useless(c: Client, msg: Message):
    user_id = msg.from_user.id
    current_time = time()

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
    
    text = ""
    if msg.text:
        text = msg.text
    elif msg.media:
        text = msg.caption

    if text:
        bot_link_pattern = r'https://(?:t(?:elegram)?\.me)/([^/\s?]+)\?start=([^\s]+)'
        matches = list(re.finditer(bot_link_pattern, text))
        if matches and user_id in pending_query:
            return await msg.reply("**Some Requests Are Already In Processing , You Have To Wait For It**" , quote=True, disable_notification=True)
        
        if matches:
            pending_query.append(user_id)

            modified_text = text
            for match in matches:
                start_message = match.group(2)
                if len(list(app.managed_bots.keys())) == 0:
                    if user_id in pending_query:
                        pending_query.remove(user_id)
                    return await msg.reply("Something Went Wrong Contact To Admin For Fix." , quote=True, disable_notification=True)
                first_bot = next(iter(app.managed_bots))
                bot_username = app.managed_bots[first_bot]['username']
                if await get_content(start_message):
                    new_link = f"https://telegram.me/{bot_username}?start={start_message}"
                    modified_text = modified_text.replace(match.group(0), new_link)
            if modified_text != text:
                temp_msg = await msg.reply_sticker("CAACAgUAAxkBAAENyhtnrs6LeKUY9DLCfmz3oib0FdlqTwACyhEAAkdcEVUUZZqNLmO-wjYE",quote=True, disable_notification=True)
                pending_query.remove(user_id)
                await temp_msg.delete()
                if msg.media:
                    await msg.copy(chat_id=user_id, caption=modified_text, disable_notification=True)
                else:
                    await msg.reply(modified_text, disable_notification=True)
                return await c.send_sticker(
                    chat_id=msg.chat.id,
                    sticker="CAACAgUAAxkBAAENv5NnqHnhkZk8Zu5TG2KqRCQCDYQC0QAC7RYAAkSUCVXXytOyyVzHkjYE",
                    disable_notification=True
                )
        
    if user_id in pending_query:
        pending_query.remove(user_id)



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
                caption=f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages,\n The Bot Will Ignore You For Next 5 Minutes.**", 
                disable_notification=True
            )
        else:
            await msg.reply_sticker("CAACAgUAAxkBAAENyjJnrucU5iUlWZjAaQAB7MCO5aVpwsgAAmkTAALatwhVlzot0t5jSDw2BA", quote=True, disable_notification=True)
            await msg.reply(f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages,\n The Bot Will Ignore You For Next 5 Minutes.**", quote=True, disable_notification=True)
        return

    # Update last message time
    user_data["last_time"] = current_time

    btn = []

    btn.append(
        [
                InlineKeyboardButton(text="𝘔𝘢𝘬𝘦 𝘈 𝘙𝘦𝘲𝘶𝘦𝘴𝘵  ", callback_data="important_start")
            ]
    )
    btn.append(
        [
            InlineKeyboardButton(text="𝘈𝘯𝘯𝘰𝘶𝘯𝘤𝘦𝘮𝘦𝘯𝘵", url = ANNOUNCMENT_LINK),
            InlineKeyboardButton(text="𝘏𝘰𝘸 𝘛𝘰 𝘍𝘪𝘯𝘥", url = "https://t.me/Ultra_XYZ/48")
        ]
    )
    btn.append(
        [
            InlineKeyboardButton(text="𝘏𝘰𝘸 𝘛𝘰 𝘜𝘴𝘦 𝘉𝘰𝘵", url = HOW_TO_USE_MAIN_BOT)
        ]
    )

    return await msg.reply_photo(
            photo= START_IMG,
            caption= UNWANTED_MESSAGES.format(msg.from_user.mention),
            reply_markup=InlineKeyboardMarkup(btn),
            quote=True,  
            disable_notification=False
            )

@app.on_callback_query(filters.regex("important_start|important_upload|important_reject"))
async def important_callback(c: Client, query: CallbackQuery):
    user_id = query.from_user.id
    
    if query.data == "important_start":
        
        # Update button to DONE
        btn = [
            [
                InlineKeyboardButton(text="𝘚𝘦𝘯𝘥", callback_data="important_upload"),
                InlineKeyboardButton(text="𝘊𝘢𝘯𝘤𝘦𝘭", callback_data="important_reject")
            ]
        ]
        try:
            await query.message.delete()
        except:
            pass
        del_message = await app.send_audio(
            chat_id=user_id,
            audio = IMPORTANT_AUDIO,
            caption =f"<pre>• Share Your Content or Content Request Below </pre> <pre>• Mention Any Issues, Suggestions, or Queries </pre> <pre>• Once You're Done, Click 'SEND BUTTON' To Forward Your Message Directly To The Admin For Review </pre> ~ @ShareCareTG", 
            reply_markup=InlineKeyboardMarkup(btn),
            disable_notification=True
            )
        important_mode[user_id] = {
            "active": True,
            "del_message":del_message,
            "messages": []
        }

    elif query.data == "important_upload":
        if user_id in important_mode:
            btn = [
                [
                    InlineKeyboardButton(text="𝖴𝗉𝗅𝗈𝖺𝖽 ", callback_data=f"admin_upload"),
                    InlineKeyboardButton(text="𝖱𝖾𝗃𝖾𝖼𝗍 ", callback_data=f"admin_reject|{user_id}"),
                ]
            ]
            messages = important_mode[user_id]["messages"]
            i = 0
            while i < len(messages):
                if messages[i].media_group_id:
                    # Collect all messages in the same media group
                    media_group = []
                    group_id = messages[i].media_group_id
                    while i < len(messages) and messages[i].media_group_id == group_id:
                        media_group.append(messages[i])
                        i += 1
                    # Forward the entire media group together
                    snt_msg = await c.forward_messages(
                        chat_id=USELESS_CHANNEL,
                        from_chat_id=user_id,
                        message_ids=[msg.id for msg in media_group]
                    )
                    await snt_msg[0].reply_text(
                        text=f"**Request Given by :** {query.from_user.mention}",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                else:
                    # Forward single message normally
                    snt_msg = await messages[i].forward(USELESS_CHANNEL)
                    i += 1
                    await snt_msg.reply_text(
                        text=f"**Request Given by :** {query.from_user.mention}",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
            
            # Clear important mode
            del important_mode[user_id]
            await query.message.delete()
            await app.send_sticker(chat_id=user_id, sticker="CAACAgUAAxkBAAEOFqxn1dGKn6iQ3hFtObDeKFeLwllrmQACGhUAAjQWeFWSS3Lgug_JYDYE", disable_notification=True)
            await app.send_message(chat_id=user_id, text="**Your Query Successfully Sent To Admin**", disable_notification=True)
    
    elif query.data == "important_reject":
        if user_id in important_mode:
            del important_mode[user_id]
            await query.message.delete()
            await app.send_sticker(chat_id=user_id, sticker="CAACAgUAAxkBAAEOFq5n1dHuf-mHpqlVvTgalQNVfnrxogACGRUAAr8UcVWl6WMo-kb3zTYE", disable_notification=True)
            await app.send_message(chat_id=user_id, text="**Your Request Successfully Rejected By You**", disable_notification=True)

import re
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from Stranger.core.paytm import get_payment_details
from Stranger.misc import SUDOERS
from Stranger import app, LOGGER
from Stranger.utils.database.mongodatabase import add_token_subscription, get_content, get_order_data
from Stranger.utils.helper import generate_unique_token, retry_with_flood_wait
from strings import ANNOUNCMENT_LINK, MB_USELESS,REPLACE_LINK_TUTORIAL, SUBS_4
from config import BANNED_USERS, IMPORTANT_AUDIO, MB_USELESS_THUMBNAIL, MULTIPLE_BOT_ALLOWED_DM, USELESS_CHANNEL, WARNING_AUDIO
from time import time

# Constants

SPAM_WARNING = "Please don't spam"
MESSAGE_COOLDOWN = 10  # seconds
SPAM_BLOCK_TIME = 300  # 5 minutes

# Track user messages
user_messages = {}  # {user_id: {"count": 0, "last_time": timestamp, "warnings": 0, "blocked_until": 0}}
important_mode = {} # {user_id: {"active": bool,"del_message":Message, "messages": []}}
_BOT_INFO_CACHE = {}

async def clear_important_mode(user_id: int) -> None:
    """Clear important mode for a user"""
    if user_id in important_mode:
        try:
            await important_mode[user_id]['del_message'].delete()
        except:
            pass

        del important_mode[user_id]

pending_query = []

@Client.on_message(~filters.regex(r'^/') & filters.private & filters.incoming & ~SUDOERS & ~BANNED_USERS & ~MULTIPLE_BOT_ALLOWED_DM)
async def handle_useless(c: Client, msg: Message):
    user_id = msg.from_user.id
    current_time = time()

    global _BOT_INFO_CACHE
    if c.name not in _BOT_INFO_CACHE:
        try:
            _BOT_INFO_CACHE[c.name] = await retry_with_flood_wait(c.get_me)
        except Exception as e:
            LOGGER(__name__).error(f"Failed to get bot info: {e}")
            return await msg.reply("Service temporarily unavailable, please try again later.")
    
    me = _BOT_INFO_CACHE[c.name]
    bot_username = me.username

    if user_id in important_mode and important_mode[user_id]["active"]:
        if msg.text and msg.text.startswith("/"):
            del important_mode[user_id]
            return
        important_mode[user_id]["messages"].append(msg)
        return
    
    if msg.text and msg.text.startswith("order"):
        order_id = msg.text.strip()
        try:
            data = await get_payment_details(order_id)
            if data:
                result = await get_order_data(order_id)
                subs_type = result['subscription_type']
                plan = result['plan_type']
                token = await generate_unique_token()
                await add_token_subscription(
                    token = token,
                    subscription_type=subs_type,
                    plan_type=plan,
                    method="payment",
                    order_id=order_id
                )
                await msg.reply_sticker("CAACAgUAAxkBAAENyiVnruLcCNELM08i23iHuXj2oW6HiAACTxQAAu3kCVVCPQhl9B4S3TYE",quote=True, disable_notification=True)
                btn=[
                [
                    InlineKeyboardButton(text="𝘈𝘤𝘵𝘪𝘷𝘢𝘵𝘦", url=f"https://telegram.dog/{bot_username}?start=verify_{token}")
                ]
                ]
                return await c.send_message(
                    chat_id=user_id,
                    text=SUBS_4.format(data['customerName']), 
                    reply_markup=InlineKeyboardMarkup(btn),
                    disable_notification=True
                )
            else:
                return await msg.reply("**YOUR TOKEN IS NOT VALID \n<pre>• Meybee Your Token Already Used By YOU</pre><pre>•Maybe Your Token Could Be Wrong Too.</pre><pre>•Maybe You're Redeeming Someone Else's Token</pre>**")
        except Exception as e:
            LOGGER(__name__).error(f"Error in checking orderid :{e}")


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
            return await msg.reply(">**Some Requests Are already In Processing , You Have To Wait For It**.",quote=True, disable_notification=True)
        
        if matches:
            pending_query.append(user_id)

            modified_text = text
            for match in matches:
                bot_usr = match.group(1)
                start_message = match.group(2)
                if bot_username != bot_usr and await get_content(start_message):
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
                    sticker="CAACAgUAAxkBAAENv5NnqHnhkZk8Zu5TG2KqRCQCDYQC0QAC7RYAAkSUCVXXytOyyVzHkjYE"
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
                caption=f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages, The Bot Will Ignore You For Next 5 Minutes.**", 
                disable_notification=True
            )
        else:
            await msg.reply_sticker("CAACAgUAAxkBAAENyjJnrucU5iUlWZjAaQAB7MCO5aVpwsgAAmkTAALatwhVlzot0t5jSDw2BA",quote=True, disable_notification=True)
            await msg.reply(f">**WARNING : {user_data['warnings']}/3 \nDue To Repeated Unnecessary Messages, The Bot Will Ignore You For Next 5 Minutes.**",quote=True, disable_notification=True)
        return

    # Update last message time
    user_data["last_time"] = current_time

    btn = [
            [
                InlineKeyboardButton(text="𝘔𝘢𝘬𝘦 𝘈 𝘙𝘦𝘲𝘶𝘦𝘴𝘵 ", callback_data="important_start")
            ],
            [
                InlineKeyboardButton(text="𝘈𝘯𝘯𝘰𝘶𝘯𝘤𝘦𝘮𝘦𝘯𝘵", url=ANNOUNCMENT_LINK),
                InlineKeyboardButton(text="𝘔𝘰𝘳𝘦 𝘓𝘪𝘯𝘬𝘴", url=f"https://t.me/{app.username}?start"),
            ],
            [
                InlineKeyboardButton(text="𝘍𝘪𝘹 𝘓𝘪𝘯𝘬 𝘛𝘶𝘵𝘰𝘳𝘪𝘢𝘭", url=REPLACE_LINK_TUTORIAL)
            ]
            
        ]
    return await msg.reply_video(
                    video= "https://envs.sh/AqS.mp4",
                    caption= MB_USELESS.format(msg.from_user.mention),
                    thumb=MB_USELESS_THUMBNAIL,
                    reply_markup=InlineKeyboardMarkup(btn),
                    quote=True, 
                    disable_notification=False
                    )

@Client.on_callback_query(filters.regex("important_start|important_upload|important_reject"))
async def important_callback(c: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if query.data == "important_start":
       
        btn = [
            [
                InlineKeyboardButton(text="𝘚𝘦𝘯𝘥", callback_data="important_upload"),
                InlineKeyboardButton(text="𝘊𝘢𝘯𝘤𝘦𝘭", callback_data="important_reject")
            ]
        ]
        await query.message.delete()
        del_message = await c.send_audio(
            chat_id=user_id,
            audio = IMPORTANT_AUDIO,
            caption =f"<pre>• Share Your Content or Content Request Below</pre>\n<pre>• Mention Any Issues, Suggestions, or Queries </pre>\n<pre>• Once You're Done, Click 'SEND BUTTON' To Forward Your Message Directly To The Admin For Review </pre> ~ @ShareCareTG", 
            reply_markup=InlineKeyboardMarkup(btn), disable_notification=True)
        important_mode[user_id] = {
            "active": True,
            "del_message": del_message,
            "messages": []
        }

    elif query.data == "important_upload":
        if user_id in important_mode:
            # Forward stored messages to channel
            btn = [
                [
                    InlineKeyboardButton(text="𝘜𝘱𝘭𝘰𝘢𝘥 ", callback_data=f"admin_upload"),
                    InlineKeyboardButton(text="𝘙𝘦𝘫𝘦𝘤𝘵 ", callback_data=f"admin_reject|{user_id}"),
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
                        text=f"**Reqested Given By :** {query.from_user.mention}",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                else:
                    # Forward single message normally
                    snt_msg = await messages[i].forward(USELESS_CHANNEL)
                    i += 1
                    await snt_msg.reply_text(
                        text=f"**Reqested Given By :** {query.from_user.mention}",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
            
            # Clear important mode
            del important_mode[user_id]
            
            await query.message.delete()
            await c.send_sticker(chat_id=user_id, sticker="CAACAgUAAxkBAAEOFqxn1dGKn6iQ3hFtObDeKFeLwllrmQACGhUAAjQWeFWSS3Lgug_JYDYE")
            await c.send_message(chat_id=user_id, text="**Your Query Successfully Sent To Admin**")
    
    elif query.data == "important_reject":
        if user_id in important_mode:
            del important_mode[user_id]
            await query.message.delete()
            await c.send_sticker(chat_id=user_id, sticker="CAACAgUAAxkBAAEOFq5n1dHuf-mHpqlVvTgalQNVfnrxogACGRUAAr8UcVWl6WMo-kb3zTYE")
            await c.send_message(chat_id=user_id, text="**Your Request Successfully Rejected By You**")

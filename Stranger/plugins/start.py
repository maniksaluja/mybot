import asyncio
import re
import random
import pytz
import datetime
from typing import List, Optional
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, CallbackQuery, InputMediaPhoto, InputMediaAudio, InputMediaVideo, InputMediaDocument
from pyrogram.errors import MessageNotModified

from Stranger import app
from Stranger.utils.database import bot_users, add_user_seen_posts, get_posts_by_date, add_post_reaction, get_post_reactions, get_unseen_posts_for_user, get_random_unseen_posts_for_user
from Stranger.utils.database.mongodatabase import cleanup_user_seen_posts_for_deleted_post, delete_post, get_settings, get_user
from Stranger.utils.helper import get_readable_time, retry_with_flood_wait
from Stranger.plugins.useless import clear_important_mode
from Stranger.plugins.tools.reaction_post import trigger_reaction_post_update
from config import BANNED_USERS, emoji, AUTO_DELETE_POST, START_IMG, FSUB_CHAT_LINKS,MAX_POSTS, temp, RFSUB_CHAT_LINKS, PENDING_REQUEST_LINKS
from Stranger import LOGGER
from Stranger.misc import SUDOERS
from strings import ANNOUNCMENT_LINK, HOW_TO_USE_MAIN_BOT, MAIN_BOT_FIRST_TIME_START_MEASSAGE, CONTENT_LOADING_STICKER, MAIN_BOT_SECOND_TIME_START_MEASSAGE


MESSAGE_DELAY = 1  # seconds

post_pending = []

active_tasks = {}
stop_requested = set()

def is_stop_requested(user_id):
    if user_id in stop_requested:
        stop_requested.remove(user_id)
        if user_id in post_pending:
            post_pending.remove(user_id)
        return True
    return False

async def get_message_safely(app: Client, channel_id: int, msg_id: int, 
                           backup_channel_id: int, backup_msg_id: int) -> Optional[Message]:
    """Safely retrieve message from primary or backup channel."""
    try:
        return await app.get_messages(channel_id, msg_id)
    except ValueError:
        try:
            return await app.get_messages(backup_channel_id, backup_msg_id)
        except Exception as e:
            LOGGER(__name__).info(f"Error fetching message: {e}")
            return None

async def delete_messages_safely(messages: List[Message]):
    """Safely delete multiple messages."""
    for msg in messages:
        try:
            await msg.delete()
        except Exception as e:
            pass

def modify_message_content(text:str, new_bot_username):
    """Modify message content with new bot username and description"""
    bot_link_pattern = r'https://(?:t(?:elegram)?\.me)/([^/\s?]+)\?start=([^\s]+)'
    match = re.search(bot_link_pattern, text)
    if match:
        start_param = match.group(2)
        new_link = f"https://telegram.me/{new_bot_username}?start={start_param}"
        modified_text = text.replace(match.group(0), new_link)
        return modified_text

@app.on_message(filters.command("start") & filters.private & ~BANNED_USERS)
async def start_cmd(client:Client, message: Message):

    if len(message.text.split()) > 1:
        query = message.text.split(" ", 1)[1]
        if query.startswith("latest_"):
            return await start_cmd_reply(client, message)

    user_id = message.from_user.id

    await clear_important_mode(user_id)

    bot_username = app.username
    keyboard = [
    ["TODAY'S CONTENT" ],
    [ "INDIAN", "GLOBAL", "DARK"],
    ["OTHERS"]
]   
    data = await get_settings()

    if data['promotion']:
        keyboard.append(["Buy Subscription"])

    button = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if not await bot_users.is_user(bot_username=bot_username, user_id=user_id):
        try:
            btn = []
            rows = []
            LINKS = {**FSUB_CHAT_LINKS, **RFSUB_CHAT_LINKS, **PENDING_REQUEST_LINKS}
            for channel, name in temp.items():
                rows.append(
                    InlineKeyboardButton(text=name, url= LINKS[channel])
                )
                if len(rows) ==2:
                    btn.append(rows)
                    rows = []
            if rows:
                btn.append(rows)
            btn.append(
                [
                    InlineKeyboardButton(text="𝖧𝗈𝗐 𝖳𝗈 𝖴𝗌𝖾 𝖡𝗈𝗍", url=HOW_TO_USE_MAIN_BOT)
                ]
            )
            await bot_users.add_user(bot_username, user_id)
            await message.reply_photo(
                        photo=START_IMG,
                        caption=MAIN_BOT_FIRST_TIME_START_MEASSAGE.format(message.from_user.mention),
                        reply_markup=InlineKeyboardMarkup(btn),
                        quote=True,
                        disable_notification=True
                    )
            await message.reply_text(".", reply_markup=button, disable_notification=True)
        except Exception as e:
            LOGGER(__name__).info(f"Error in start msg in main bot :{e}")
            pass
    else:
        btn = [
            [
                InlineKeyboardButton("𝖠𝗇𝗇𝗈𝗎𝗇𝖼𝖾𝗆𝖾𝗇𝗍", url = ANNOUNCMENT_LINK)
            ],
            [
                InlineKeyboardButton("𝖦𝖾𝗍 𝖦𝗎𝗂𝖽𝖾 𝖵𝗂𝖽𝖾𝗈", url=HOW_TO_USE_MAIN_BOT)
            ],
        ]
        await message.reply_photo(
            photo=START_IMG,
            caption=MAIN_BOT_SECOND_TIME_START_MEASSAGE.format(message.from_user.mention),
            disable_notification=True,
            quote=True,
            reply_markup=InlineKeyboardMarkup(btn),
            )
        await message.reply_text("..", reply_markup=button, disable_notification=True)

@app.on_message(filters.regex(pattern=r"(?i)^(TODAY'S CONTENT|INDIAN|GLOBAL|DARK|OTHERS|Buy Subscription)$") & ~BANNED_USERS)
async def start_cmd_reply(client: Client, message: Message):

    user_id = message.from_user.id
    global post_pending

    await clear_important_mode(user_id)

    if message.text == "TODAY'S CONTENT":
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)
        query = f"latest_{current_time.strftime('%Y_%m_%d')}"
    elif message.text == "INDIAN":  
        query = "indian"
    elif message.text == "GLOBAL":    
        query = "global"
    elif message.text == "DARK":     
        query = "dark"
    elif message.text == "OTHERS":
        query = "others"
    elif message.text == "Buy Subscription":
        data = await get_settings()
        if not data['promotion']:
            return
        try:
            ad_media = data['promotion_data']
            if len(ad_media) > 1:
                # Send media group
                media_items =[]
                for ad in ad_media:
                    if ad['type'] == 'photo':
                        media_items.append(
                            InputMediaPhoto(
                                media=ad['file_id'],
                                caption=ad['caption']
                            )
                        )
                    elif ad['type'] == 'video':
                        media_items.append(
                            InputMediaVideo(
                                media=ad['file_id'],
                                caption=ad['caption']
                                )
                                )
                    elif ad['type'] == 'document':
                        media_items.append(
                            InputMediaDocument(
                                media=ad['file_id'],
                                caption=ad['caption']
                                )
                        )
                    elif ad['type'] == 'audio':
                        media_items.append(
                            InputMediaAudio(
                                media=ad['file_id'],
                                caption=ad['caption']
                                )
                                )
                # Send the media group
                await client.send_media_group(
                    chat_id=user_id,
                    media=media_items
                )
            else:
                ad = ad_media[0]
                media_type = ad.get('type', 'text')
                file_id = ad.get('file_id', 0)
                caption = ad.get('caption', '')

                if media_type == 'text':
                    # Send text message
                    await client.send_message(chat_id=user_id, text=caption)

                elif media_type == 'photo':
                    # Send photo
                    await client.send_photo(
                        chat_id=user_id,
                        photo=file_id,
                        caption=caption
                    )

                elif media_type == 'video':
                    # Send video
                    await client.send_video(
                        chat_id=user_id,
                        video=file_id,
                        caption=caption
                    )

                elif media_type == 'document':
                    # Send document
                    await client.send_document(
                        chat_id=user_id,
                        document=file_id,
                        caption=caption
                    )

                elif media_type == 'audio':
                    # Send audio
                    await client.send_audio(
                        chat_id=user_id,
                        audio=file_id,
                        caption=caption
                    )

                elif media_type == 'sticker':
                    # Send sticker (no caption for stickers)
                    await client.send_sticker(
                        chat_id=user_id,
                        sticker=file_id
                    )

                elif media_type == 'voice':
                    # Send voice
                    await client.send_voice(
                        chat_id=user_id,
                        voice=file_id,
                        caption=caption
                    )

        except Exception as e:
            LOGGER(__name__).error(f"Error sending advertisement: {e}")
        return
    elif message.text.split(" ", 1)[1].startswith("latest_"):
        query = message.text.split(" ", 1)[1]
    else:
        return

    if user_id in post_pending:
        return await message.reply("**Request Is Already Running:**\n>**The System Will Process A New One Only After The Current One Is Completed Or Stopped.**", quote=True, disable_notification=True)
    else:
        post_pending.append(user_id)

    try:
        bots = app.managed_bots
    
        if len(list(app.managed_bots.keys())) == 0:
            post_pending.remove(user_id)
            return await message.reply_text("**No Bot Available**", quote=True, disable_notification=True)

        temp_msg1 = await message.reply_sticker(CONTENT_LOADING_STICKER, quote=True, disable_notification=True)
        sent_messages: List[Message] = []
               
        bot = random.choice(list(bots.keys()))
        bot_username = bots[bot]['username']

        if query.startswith("latest_"):
            date_str = query.split("_", 1)[1]
            links = await get_posts_by_date(date_str)
            posts_to_send = links  # For latest posts, we don't filter seen posts
        else:
            posts_to_send = await get_unseen_posts_for_user(
                user_id=user_id,
                category=query,
                limit=10,
                exclude_today=True
            )

        if not posts_to_send:
            post_pending.remove(user_id)
            await delete_messages_safely([temp_msg1])
            return await message.reply_text("**No Data In This Category**", quote=True, disable_notification=True)

        newly_seen_posts = []
        try:
            for i, post in enumerate(posts_to_send):
                if is_stop_requested(user_id):
                    await message.reply_text("**Running Process Stopped!!**.", quote=True, disable_notification=True)
                    break
                
                new_caption = modify_message_content(post['caption'], bot_username)
                
                btn = []

                if user_id in SUDOERS:
                    btn.append([
                            InlineKeyboardButton(
                            text="🗑️ DELETE POST",
                                callback_data=f"DELETE_POST|{post['post_id']}"
                            )
                            ])
                
                if i < len(posts_to_send) - 1:
                    btn.append([InlineKeyboardButton("𝘚𝘵𝘰𝘱 𝘍𝘰𝘳𝘸𝘢𝘳𝘥𝘪𝘯𝘨 ", callback_data=f"stop_content")])
                
                sent_msg = await retry_with_flood_wait(
                    app.send_photo,
                    chat_id=user_id,
                    photo=post['thumblink'],
                    caption=new_caption,
                    reply_markup=InlineKeyboardMarkup(btn) if btn else None,
                    disable_notification=True
                )
                sent_messages.append(sent_msg)
                
                # Only track seen posts for non-latest queries
                if not query.startswith("latest_"):
                    newly_seen_posts.append(post['post_id'])
                
                await asyncio.sleep(MESSAGE_DELAY)
        except Exception as e:
            LOGGER(__name__).info(f"Error sending message: {e}")
        
        # Add to seen posts only for non-latest queries
        if newly_seen_posts and not query.startswith("latest_"):
            await add_user_seen_posts(user_id, newly_seen_posts)

        if user_id in post_pending:
            post_pending.remove(user_id)

        if temp_msg1:
            await delete_messages_safely([temp_msg1])

        user = await get_user(user_id)

        if AUTO_DELETE_POST:
            if user['is_download_verified']:
                await message.reply_text(
                        "You are a premimum user, So auto delete message is disabled for you!!!", disable_notification=True
                    )
            else:
                temp_msg2 = await app.send_message(
                    chat_id=message.chat.id,
                    text=f">**Posts Will Be Deleted After** {get_readable_time(AUTO_DELETE_POST)}**",
                    disable_notification=True
                )

                asyncio.create_task(auto_delete_posts(
                    client=app,
                    messages=sent_messages + ([temp_msg2] if temp_msg2 else []),
                    delay=AUTO_DELETE_POST
                ))
        return
    except Exception as e:
        LOGGER(__name__).info(f"Error in handle_category_request: {e}")
        if user_id in post_pending:
            post_pending.remove(user_id)
        try:
            await message.reply_text(text = "An error occurred while processing your request.", disable_notification=True)
        except:
            pass
        return


@app.on_callback_query(filters.regex("DELETE_POST") & SUDOERS)
async def delete_post_callback(client: Client, callback_query: CallbackQuery):
    """Handle post deletion by SUDOERS"""
    try:
        post_id = callback_query.data.split("|")[1]
        
        deletion_success = await delete_post(post_id)

        if deletion_success:
            await cleanup_user_seen_posts_for_deleted_post(post_id)
            await callback_query.answer("✅ Post deleted successfully!", show_alert=True)
            asyncio.sleep(3)
            try:
                await callback_query.message.delete()
            except:
                pass
            
        else:
            await callback_query.answer("❌ Failed to delete post from database!", show_alert=True)
            
    except Exception as e:
        await callback_query.answer("❌ Error deleting post!", show_alert=True)
        print(f"Error deleting post: {e}")
    
    return

async def auto_delete_posts(client: Client, messages: List[Message], delay: int):
    """Handle auto-deletion of messages without blocking the main handler"""
    try:
        await asyncio.sleep(delay)
        await delete_messages_safely(messages)
    except Exception as e:
        LOGGER(__name__).info(f"Error in auto_delete_posts: {e}")

@app.on_message(filters.command("stop") & filters.private & ~BANNED_USERS)
async def stop_content_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    
    if user_id in post_pending:
        stop_requested.add(user_id)
        await message.reply("**Stopping Content Delivery..**", quote=True)
    else:
        await message.reply("**No Active Content Delivery To Stop.**", quote=True)

@app.on_callback_query(filters.regex("stop_content"))
async def stop_content_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    if user_id in post_pending:
        stop_requested.add(user_id)
        await callback_query.answer("Stopping Content Delivery...")
        
        try:
            await callback_query.edit_message_reply_markup(None)
        except:
            pass
    else:
        await callback_query.answer("No Active Content Delivery To Stop")

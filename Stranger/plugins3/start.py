import random
import pytz
import time
import asyncio
import datetime
from typing import List, Optional
from cachetools import TTLCache

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatMemberUpdated, ChatJoinRequest
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait, MessageIdInvalid, InputUserDeactivated, UserIsBlocked, MediaEmpty, MessageNotModified, FileReferenceExpired

from Stranger import userbot, shotner
from Stranger.plugins.tools.reaction_post import trigger_reaction_post_update
from Stranger.utils.database.mongodatabase import add_post_reaction, update_order, get_post_by_content_id, update_content_field
from Stranger.utils.helper import generate_unique_token, get_media_data, get_readable_time, retry_with_flood_wait
from Stranger.utils.database import manage_users, user_exists, is_user_requested, get_user, set_user_field, update_user, add_subscription, get_content, get_settings, bot_users, Plan, Subs_Type
from Stranger.utils.file_manager import file_manager
from Stranger import app
from Stranger.core.razorpay import create_order, get_payment_details
from Stranger.plugins3.useless import clear_important_mode
from Stranger.logger import LOGGER

from config import *

from strings import *


SLEEP_DELAY = 1
OWNER_WARNING = 0

file_count_cache = TTLCache(maxsize=20000, ttl=86400)  # 24 hour TTL
files_to_send = set()

def get_cache_key(user_id: int) -> str:
    """Generate cache key with date to auto-expire at midnight"""
    today = datetime.date.today().isoformat()
    return f"{user_id}:{today}"

def get_today_file_count(user_id: int) -> int:
    """Get user's file count for today with caching"""
    cache_key = get_cache_key(user_id)
    return file_count_cache.get(cache_key, 0)

def increment_file_count(user_id: int) -> None:
    """Increment user's file count for today"""
    cache_key = get_cache_key(user_id)
    current_count = file_count_cache.get(cache_key, 0)
    file_count_cache[cache_key] = current_count + 1

async def _try_backup_from_userbot_two(file: dict) -> Optional[str]:
    """Check if backup processing is available and start if needed"""
    try:
        content_id = file['_id']
        
        # Check if backup is already being processed
        if file_manager.is_backup_processing(content_id):
            return "processing"
        
        # Check if files are available in userbot.two
        contents = file.get('contents', [])
        has_backup_files = False
        
        for content in contents:
            userbot_two_data = content.get('userbot_two_data', {})
            if userbot_two_data and userbot_two_data.get('msg_id'):
                has_backup_files = True
                break
        
        if not has_backup_files:
            return None
        
        # Start background backup processing
        asyncio.create_task(file_manager.start_backup_processing(content_id, file))
        return "started"
        
    except Exception as e:
        LOGGER(__name__).error(f"Error in backup from userbot.two: {e}")
        return None

# Track pending subscription checks with channels that need to be joined
subscription_checks = {}

async def get_pending_channels(client: Client, user_id: int) -> list[int]:
    """Get list of channels user hasn't joined yet"""
    pending = []
    for channel_id in temp_channels:
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER):
                if not await is_user_requested(user_id, channel_id):
                    pending.append(channel_id)
        except Exception:
            if not await is_user_requested(user_id, channel_id):
                pending.append(channel_id)
    return pending

async def check_subscription_status(client: Client, user_id: int, timeout: int = 15):
    """Create a future to track subscription completion with pending channels"""
    future = asyncio.Future()
    pending_channels = await get_pending_channels(client, user_id)
    
    if not pending_channels:
        return True
        
    subscription_checks[user_id] = {
        'future': future,
        'deadline': time.time() + timeout,
        'pending_channels': set(pending_channels)  # Use set for O(1) lookup/removal
    }
    try:
        return await asyncio.wait_for(future, timeout)
    except asyncio.TimeoutError:
        return False
    finally:
        subscription_checks.pop(user_id, None)

@Client.on_chat_member_updated(filters.chat(temp_channels))
async def handle_member_updates(client: Client, update: ChatMemberUpdated):
    
    user_id = update.from_user.id
    
    if user_id not in subscription_checks:
        return
    
    if update.chat.id not in temp_channels:
        return
    
    if not update.new_chat_member:
        return
    
    

    # Remove channel from pending list
    subscription_checks[user_id]['pending_channels'].discard(update.chat.id)
    
    # If no more pending channels, complete the future
    if not subscription_checks[user_id]['pending_channels']:
        future = subscription_checks[user_id]['future']
        if not future.done():
            future.set_result(True)

@Client.on_chat_join_request(filters.chat(temp_channels)) 
async def handle_join_requests(client: Client, join_request: ChatJoinRequest):
    if join_request.chat.id not in temp_channels:
        return
    
    user_id = join_request.from_user.id
    if user_id not in subscription_checks:
        return

    # Remove channel from pending list
    subscription_checks[user_id]['pending_channels'].discard(join_request.chat.id)
    
    # If no more pending channels, complete the future
    if not subscription_checks[user_id]['pending_channels']:
        future = subscription_checks[user_id]['future']
        if not future.done():
            future.set_result(True)

pending_requests = TTLCache(maxsize=1000, ttl=300)  # 5 minute TTL

def reaction_button(data: dict, post_id: str = None):
    """Create reaction buttons for a post"""
    btn = []
    rows = []
    for em in emoji:
        cn = data.get(em, 0)
        callback_data = f"POST_REACTION|{post_id}|{em}"
        rows.append(
            InlineKeyboardButton(
                text=f"{emoji[em]} {'' if cn == 0 else cn}",
                callback_data=callback_data
            )
        )
        if len(rows) == 4:
            btn.append(rows)
            rows = []
    if rows:
        btn.append(rows)
    
    return btn 

@Client.on_message(filters.command("start") & filters.private & ~BANNED_USERS)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    await clear_important_mode(user_id)

    global files_to_send
    bot_username = client.me.username
    
    if not await user_exists(user_id):
        try:
            await manage_users(user_id, 'add')
        except Exception as e:
            LOGGER(__name__).info(f"Failed to add user {user_id}: {e}")
    
    user = await get_user(user_id)

    if (user['is_token_verified'] and time.time() > user['token_expiry_time']) or (user['is_download_verified'] and time.time() > user['download_expiry_time']):
        if user['is_token_verified'] and time.time() > user['token_expiry_time']:
            user["is_token_verified"] = False
            user["token_plan"] = 'None'
            user["token_expiry_time"] = 0
            user['access_token_type'] = 'None'
        if user['is_download_verified'] and time.time() > user['download_expiry_time']:
            user['is_download_verified'] = False
            user['download_plan'] = 'None'
            user['download_expiry_time'] = 0
            user['access_download_type'] = 'None'
        await update_user(user_id, user)

    settings = await get_settings()
    access = settings['access_token']

    if "check_" in message.text:
        _, token = message.text.split("_", 1)
        if token and user['token_verify_token'] != token:
            return await message.reply_text("** YOUR TOKEN IS NOT VALID \n<pre>• Meybee Your Token Already Used By SomeOne</pre>\n<pre>•Maybe Your Token Could Be Wrong Too.</pre><pre>•Maybe You're Redeeming Someone Else's Token</pre>**", disable_notification=True)
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)

        user['is_token_verified'] = True
        user['token_plan'] = 'plan1'
        user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_1 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_1
        user['access_token_type'] = 'ads'
        user['token_verify_token'] = ""
        await add_subscription('access', 'plan1', 'ads', user_id)
        await message.reply_sticker("CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE", disable_notification=True)
        await message.reply(f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()} \n•SUBSCRIPTION TYPE: ADS \n>• Expires In : {get_readable_time(ACCESS_TOKEN_PLAN_1)} **", disable_notification=True)

        await update_user(user_id, user)
        return

    elif "pay_" in message.text:
        _, order_id, old_msg_id = message.text.split("_")

        try:
            await client.delete_messages(chat_id=user_id, message_ids=int(old_msg_id))
        except:
            pass
        
        result = await get_payment_details(order_id)
        subs_type = result['subscription_type']
        plan = result['plan_type']
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)

        if result["activated"]:
            return await message.reply_text("** YOUR TOKEN IS NOT VALID \n<pre>• Meybee Your Token Already Used By SomeOne</pre>\n<pre>•Maybe Your Token Could Be Wrong Too.</pre><pre>•Maybe You're Redeeming Someone Else's Token</pre>**", disable_notification=True)

        if result['status'] in ['expired', 'cancelled']:

            btn = [
            [
                InlineKeyboardButton(text="𝘛𝘳𝘺 𝘈𝘨𝘢𝘪𝘯", callback_data=f"payment|{subs_type}|{plan}"),
                InlineKeyboardButton(text="𝘏𝘦𝘭𝘱 𝘋𝘦𝘴𝘬", url=PAYMENT_HELP)
            ]
        ]
            return await client.send_video(
            chat_id=chat_id,
            video="https://envs.sh/n1W.mp4",
            thumb=PAYMENT_THUMBNAIL,
            caption = ">**ITS LOOKS LIKE YOUR PAYMENT IS STILL PENDING...\n  If You're Experiencing Any Issues, You Can\n Follow The Tutorial Above Or Contact The \nHelp Desk To Get In Touch With An Admin\nFor Support.\n\n>If The ACTIVATE Button Isn't Visible After Payment, It May Be Because The Payment Was Made More Than 5 Minutes After Receiving The QR Code. The BOT Can't Provide The Button If The Payment Is Delayed.\n Send The ORDER ID (ORDERXXXX) To The \n TERABOX BOT To Activate It**",
            reply_markup=InlineKeyboardMarkup(btn), disable_notification=True
            )
        elif result['status'] == 'created':
            btn = [
            [
                InlineKeyboardButton(text="𝘛𝘳𝘺 𝘈𝘨𝘢𝘪𝘯", url=result['pay_url']),
            ],[
                InlineKeyboardButton(
                text="Refresh",
                callback_data=f"refresh|{order_id}"
            ),
                InlineKeyboardButton(text="𝘏𝘦𝘭𝘱 𝘋𝘦𝘴𝘬", url=PAYMENT_HELP)
            ]
            ]
            return await message.reply(
                text="Payment not done yet!!! Retry again",
                reply_markup=InlineKeyboardMarkup(btn)
            )
        
        if subs_type == "access_token":
            if plan == "plan1":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_1 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_1
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN1
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_1)
                await add_subscription('access', Plan.PLAN1, 'payment', user_id)
            elif plan == "plan2":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_2 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_2
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN2
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_2)
                await add_subscription('access', Plan.PLAN2, 'payment', user_id)
            user['access_token_type'] = Subs_Type.TYPE2
            await message.reply_sticker("CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE", disable_notification=True)
            await message.reply(
                text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                disable_notification=True
                )
        elif subs_type == "download":
            if plan == "plan1":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_1 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_1
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN1
                expiry = get_readable_time(DOWNLOAD_PLAN_1)
                await add_subscription('download',Plan.PLAN1, 'payment' ,user_id)
            elif plan == "plan2":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_2 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_2
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN2
                expiry = get_readable_time(DOWNLOAD_PLAN_2)
                await add_subscription('download',Plan.PLAN2, 'payment', user_id)
            
            user['access_download_type'] = Subs_Type.TYPE2
            await message.reply_sticker("CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE")
            await message.reply(
                text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                disable_notification=True
                )
            
        await update_order(order_id, "activated", True)
        await update_user(user_id, user)
        return

    elif len(message.text) > 7:
        if not await bot_users.is_user(bot_username=bot_username, user_id=user_id):
            try:
                await bot_users.add_user(bot_username, user_id)
            except:
                pass
        if not "promo_" in message.text:
            if user_id in subscription_checks:
                is_subscribed_now = await check_subscription_status(client, user_id)
            else:
                pending_channels = await get_pending_channels(client, user_id)

                if not pending_channels:
                    is_subscribed_now = True
                else:
                    # Show join buttons first
                    btn = []
                    row = []
                    links = {**RFSUB_CHAT_LINKS, **FSUB_CHAT_LINKS, **PENDING_REQUEST_LINKS}
                    for channel in pending_channels:
                        row.append(InlineKeyboardButton(text=temp[channel], url=links[channel]))
                        if len(row) == 2:
                            btn.append(row)
                            row = []
                    if row:
                        btn.append(row)

                    btn.append(
                        [
                            InlineKeyboardButton(text="𝘏𝘰𝘸 𝘛𝘰 𝘜𝘴𝘦 𝘛𝘦𝘳𝘢𝘉𝘰𝘹", url=MB_START_TUTORIAL),
                        ]
                    )
                    
                    temp_msg = await message.reply_web_page(
                        text = MB_START_2.format(message.from_user.mention),
                        url= SUBS_IMG_1,
                        reply_markup=InlineKeyboardMarkup(btn),
                        quote=True,
                        disable_notification=True,
                        )

                    # Now start subscription check
                    is_subscribed_now = await check_subscription_status(client, user_id)

            try:
                await temp_msg.delete()
            except:
                pass

            if not is_subscribed_now:
                return
            
        if user_id in pending_requests:
            return await message.reply(">**Wait For The Running Request To Finish** ", quote=True)    
        
        try:
            if "promo_" in message.text:
                _, query = message.text.split("_", 1)
                file_id = query.strip()
                file = await get_content(file_id)
                if not file:
                    return await message.reply_sticker("CAACAgUAAxkBAAEN345nuV3aFIZ0_z18xjAFfJIegVRAAgACXxMAAmAkeVXgbAPgeJeGyzYE", disable_notification=True)
                if not file['promo_link']:
                    return await message.reply_sticker("CAACAgUAAxkBAAEN345nuV3aFIZ0_z18xjAFfJIegVRAAgACXxMAAmAkeVXgbAPgeJeGyzYE", disable_notification=True)
                can_access = True
            else:
                file_id = str(message.text.split(" ",1)[1])
                file = await get_content(file_id)
                if not file:
                    return await message.reply_sticker("CAACAgUAAxkBAAEN345nuV3aFIZ0_z18xjAFfJIegVRAAgACXxMAAmAkeVXgbAPgeJeGyzYE", disable_notification=True)
                
                if not access:
                    can_access = True 
                else:
                    file_count = get_today_file_count(user_id)
                    if file_count < DAILY_FREE_CONTENT:
                        can_access = True  
                        increment_file_count(user_id)
                    else:
                        can_access = user['is_token_verified'] 
            
            if not can_access:
                btn =[
                    [
                        InlineKeyboardButton('𝘏𝘰𝘸 𝘛𝘰 𝘎𝘦𝘵 𝘈𝘤𝘤𝘦𝘴𝘴𝘒𝘦𝘺', url=SUBS_LINK_1)
                    ]
                ]

                rows = []
                if settings['url_shortner'] or settings['payment_gateway']:
                    rows.append(
                            InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_1)}",callback_data=f"access_token_subscribe")
                    )
                if settings['payment_gateway']:
                    rows.append(
                        InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_2)}",callback_data="payment|access_token|plan2")
                    )
                if rows:
                    btn.append(rows)

                btn.append(
                    [
                        InlineKeyboardButton("𝘞𝘩𝘺 𝘕𝘦𝘦𝘥 𝘛𝘩𝘪𝘴?", url=WHY__BTN_LINK),
                        
                    ]
                )
                return await message.reply_text(
                    text=SUBS_1.format(message.from_user.mention), 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    disable_notification=True
                    )
            
            temp_msg = await message.reply_sticker(CONTENT_WAIT_STICKER, disable_notification=True)
            contents = file['contents']
            try_backup_1 = False
            try_backup_2 = False
            bot_id = client.me.id
            snt_msgs = []
            
            download_setting = settings['downloads']
            user_download = user['is_download_verified']
            
            if "promo_" in message.text:
                promo_link = file['promo_link']
                download_btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton("𝘕𝘦𝘹𝘵 𝘗𝘢𝘳𝘵🤤", url=f'https://t.me/{bot_username}?start={promo_link}')]
                ])
                protect_content = False
            else:
                protect_content = PROTECT_CONTENT and not user_download
                
                if download_setting and not user_download:
                    download_btn = InlineKeyboardMarkup([
                        [InlineKeyboardButton("𝘋𝘰𝘸𝘯𝘭𝘰𝘢𝘥 ", callback_data="download_subscribe")]
                    ])
                else:
                    download_btn = None

            for content in contents:
                try:
                    bot_data = content['bot_data'][str(bot_id)]
                    if not bot_data:
                        try_backup_1 = True
                        break
                    try:
                        for _ in range(3):
                            try:
                                snt_msg = await client.send_cached_media(
                                    chat_id=user_id,
                                    file_id=bot_data['file_id'],
                                    caption= f"{DEFAULT_CAPTION} \n{bot_data['caption']}",
                                    protect_content=protect_content,
                                    reply_markup=download_btn, 
                                    disable_notification=True
                                )
                                snt_msgs.append(snt_msg)
                                break
                            except FloodWait as fw:
                                await asyncio.sleep(int(fw.value))
                            except UserIsBlocked:
                                break
                            except MediaEmpty:
                                try_backup_1 = True
                                break
                            except Exception as e:
                                raise
                    except:
                        pass

                    if try_backup_1:
                        break
                except:
                    try_backup_1 = True
                    break
                await asyncio.sleep(SLEEP_DELAY)
            
            if len(snt_msgs) == 0 and not try_backup_1:
                try:
                    del pending_requests[user_id]
                except KeyError:
                    pass
                return await temp_msg.edit("Something went wrong..!")
            
            if try_backup_1:
                await temp_msg.delete()
                temp_msg = await client.send_message(chat_id=user_id, text="Trying for backup files ....")
                btn = [[
                            InlineKeyboardButton("Try again", url=f"https://telegram.me/{bot_username}?start={file['_id']}")
                        ]]
                try:
                    is_that_userbot_one = int(contents[0]['userbot_one_data']['user_id']) == int(userbot.one.me.id)
                    is_that_userbot_two = int(contents[0]['userbot_two_data']['user_id']) == int(userbot.two.me.id)

                    if try_backup_1 and is_that_userbot_one:
                        for content_index, content in enumerate(contents):
                            caption = content['userbot_one_data']['caption']
                            updated_caption = caption.replace("content_index=PLACEHOLDER", f"content_index={content_index}")
                            for btoken, bot_info in app.managed_bots.items():
                                try:
                                    await userbot.one.send_cached_media(
                                        chat_id=bot_info['username'],
                                        file_id=content['userbot_one_data']['file_id'],
                                        caption=updated_caption
                                    )
                                    await asyncio.sleep(0.2)
                                except (MediaEmpty, FileReferenceExpired):
                                    try:
                                        msg = await userbot.one.get_messages(chat_id="me", message_ids=int(content['userbot_one_data']['msg_id']))
                                        media_data = get_media_data(msg)

                                        await userbot.one.send_cached_media(
                                        chat_id=bot_info['username'],
                                        file_id=media_data['file_id'],
                                        caption=updated_caption
                                        )
                                        content['userbot_one_data']['file_id'] = media_data['file_id']
                                        
                                        await update_content_field(file['_id'], f"contents.{content_index}.userbot_one_data.file_id", media_data['file_id'])
                                        
                                        await asyncio.sleep(0.2)
                                    except Exception as e:
                                        try_backup_2 = True
                                        break
                                except Exception as e:
                                    LOGGER(__name__).error(f"Error sending to bot {bot_info['username']}: {e}")
                                    continue
                            if try_backup_2:
                                break

                        return await temp_msg.edit("Content has been Backed up successfully. \nTry again here", reply_markup=InlineKeyboardMarkup(btn))
                    else:
                        try_backup_2 = True

                    if try_backup_2 and is_that_userbot_two:
                        backup_result = await _try_backup_from_userbot_two(file)
                        if backup_result == "processing":
                            return await temp_msg.edit("⏳ Backup files are currently being processed. Please try again in a few minutes.", reply_markup=InlineKeyboardMarkup(btn))
                        elif backup_result == "started":
                            return await temp_msg.edit("🔄 Backup processing started. Please try again in 2-5 minutes while we prepare your files.", reply_markup=InlineKeyboardMarkup(btn))
                        elif backup_result is None:
                            return await temp_msg.edit("❌ No backup files available for this content.")
                    else:
                        return await temp_msg.edit("Something went wrong..!")
                except:
                    return await temp_msg.edit("Something went wrong..!")
                
            try:
                del pending_requests[user_id]
            except KeyError:
                pass

            try:
                await temp_msg.delete()
            except:
                pass

            post_data = await get_post_by_content_id(content_id=file['_id'])
            reaction_btns = reaction_button(post_data.get('reactions', {}), post_data['post_id'])

            feedback_text = "**Please Share You're Valuable FeedBack **\n>**Your Feedback Is Valuable! It Helps Improve** \n>**Content Quality And Benefits Others As Well.**\n>**Share Your Thoughts And Help Us Improve!!** \n\n"
            effect_id = random.choice([5107584321108051014, 
                                       5159385139981059251,
                                       5104841245755180586,
                                       5046509860389126442
                                       ])
            
            if AUTO_DELETE_CONTENT:
                delete_text = AUTO_DELETE_TEXT.format(get_readable_time(AUTO_DELETE_CONTENT))
                full_message = feedback_text + delete_text
                
                temp_msg = await message.reply_text(
                    text=full_message, 
                    reply_markup=InlineKeyboardMarkup(reaction_btns),
                    message_effect_id=effect_id,
                    disable_notification=True
                )
                asyncio.create_task(auto_delete_messages(
                    client=client, 
                    snt_msgs=snt_msgs, 
                    temp_msg=temp_msg, 
                    file=file, 
                    bot_username=bot_username, 
                    delay=AUTO_DELETE_CONTENT
                ))
            else:
                await message.reply_text(
                    text=feedback_text, 
                    reply_markup=InlineKeyboardMarkup(reaction_btns),
                    message_effect_id=effect_id,
                    disable_notification=True
                )
        except Exception as e:
            LOGGER(__name__).info(f"Error : {e}")
        finally:
            try:
                del pending_requests[user_id]
            except KeyError:
                pass
    else:
        if not await bot_users.is_user(bot_username=bot_username, user_id=user_id):

            btn = []
            row =[]
            
            links = {**RFSUB_CHAT_LINKS, **FSUB_CHAT_LINKS, **PENDING_REQUEST_LINKS}

            for channel, name in temp.items():
                row.append(InlineKeyboardButton(text=name, url=links[channel]))
                if len(row) == 2:
                    btn.append(row)
                    row = []
            
            if row:
                btn.append(row)

            btn.append(
                [InlineKeyboardButton("𝘏𝘰𝘸 𝘛𝘰 𝘜𝘴𝘦 𝘛𝘦𝘳𝘢𝘉𝘰𝘹", url=MB_START_TUTORIAL)]
            )

            try:
                await bot_users.add_user(bot_username, user_id)
                await message.reply_video(
                video= START_GIF,
                caption= MB_START_1.format(message.from_user.mention),
                reply_markup=InlineKeyboardMarkup(btn), 
                quote=True,
                disable_notification=True,
                )
            except Exception as e:
                LOGGER(__name__).info(f"Error : {e}")
                pass
        else:
            #  user verified and send /start cmd without any file id
            reply_markup = InlineKeyboardMarkup(
                [
                  [InlineKeyboardButton("𝘔𝘰𝘳𝘦 𝘊𝘰𝘯𝘵𝘦𝘯𝘵",url=f"https://t.me/{app.username}?start"),
                   InlineKeyboardButton("𝘈𝘯𝘯𝘰𝘶𝘯𝘤𝘦𝘮𝘦𝘯𝘵",url=ANNOUNCMENT_LINK)],
                  [InlineKeyboardButton("𝘏𝘰𝘸 𝘛𝘰 𝘜𝘴𝘦 𝘛𝘦𝘳𝘢𝘉𝘰𝘹", url=MB_START_TUTORIAL)]
                  ]
            )
            await message.reply_video(
                video=BASE_GIF,
                caption=MB_START_3.format(message.from_user.mention),
                reply_markup=reply_markup,
                quote=True, 
                disable_notification=True
            )
        
@Client.on_callback_query(filters.regex("access_token_help"))
async def subscribe(client:Client, callback_query:CallbackQuery):
    settings = await get_settings()
    btn = []
    rows = []
    if settings['url_shortner'] or settings['payment_gateway']:
        rows.append(
                InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_1)}",callback_data=f"access_token_subscribe")
        )
    if settings['payment_gateway']:
        rows.append(
            InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_2)}",callback_data="payment|access_token|plan2")
        )

    if rows:
        btn.append(rows)
    btn.append(
                [
                    InlineKeyboardButton("𝘞𝘩𝘺 𝘕𝘦𝘦𝘥 𝘛𝘩𝘪𝘴?", url=WHY__BTN_LINK),
                    
                ]
            )
    btn.append(
        [
                    InlineKeyboardButton('𝘏𝘰𝘸 𝘛𝘰 𝘎𝘦𝘵 𝘈𝘤𝘤𝘦𝘴𝘴𝘒𝘦𝘺', url=SUBS_LINK_1)
                ]
    )
    return await callback_query.edit_message_text(
        text=SUBS_1.format(callback_query.from_user.mention), 
        reply_markup=InlineKeyboardMarkup(btn)
        )

@Client.on_callback_query(filters.regex("access_token_subscribe"))
async def token_subscribe(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await get_user(user_id)
    
    settings = await get_settings()

    rows = []
    if settings['url_shortner']:
        try:
            token = await generate_unique_token()
            await set_user_field(user_id, 'token_verify_token', token)
            callback_url = f'https://telegram.dog/{client.me.username}?start=check_{token}'
            ad_link = await shotner.convert(link=callback_url)
            rows.append(
                InlineKeyboardButton(text = "𝘞𝘢𝘵𝘤𝘩 𝘈𝘥𝘴", url=ad_link)
            )
        except:
            rows.append(
                InlineKeyboardButton(text="Check here", callback_data="shortner_error")
            )
    
    if settings['payment_gateway']:
        rows.append(
            InlineKeyboardButton(text = "𝘋𝘪𝘳𝘦𝘤𝘵 𝘗𝘢𝘺" , callback_data="payment|access_token|plan1")
        )
    btn = []
    if rows:
        btn.append(rows)

    s_rows = []
    if settings['url_shortner']:
        s_rows.append(InlineKeyboardButton('☝🏻𝘏𝘰𝘸?', url="https://t.me/UserHelpTG/5"))
    if settings['payment_gateway']:
        s_rows.append(InlineKeyboardButton('☝🏻𝘏𝘰𝘸?', url="https://t.me/Ultra_XYZ/55" ))
    
    if s_rows:
        btn.append(s_rows)

    btn.append(
        [
            InlineKeyboardButton('𝘉𝘢𝘤𝘬', callback_data="access_token_help")
        ]
    )

    return await callback_query.edit_message_text(
        text=SUBS_2,
        reply_markup=InlineKeyboardMarkup(btn)
        )

@Client.on_callback_query(filters.regex("download_subscribe"))
async def download_subscribe(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await get_user(user_id)
    if user['is_download_verified']:
        return await callback_query.answer("Your Download Plan Is Already Active", show_alert=True)
    
    settings = await get_settings()
    
    if not settings['payment_gateway']:
        return await callback_query.answer("Payment Gateway Is Not Enabled. Please Contact Admin", show_alert=True)
    btn = [
        [InlineKeyboardButton(f"{get_readable_time(DOWNLOAD_PLAN_1)} -- Rs{DOWNLOAD_PLAN_1_PRICE}", callback_data=f"payment|download|plan1"),
        InlineKeyboardButton(f"{get_readable_time(DOWNLOAD_PLAN_2)} -- Rs{DOWNLOAD_PLAN_2_PRICE}", callback_data=f"payment|download|plan2")],
        [InlineKeyboardButton(text="𝘘𝘶𝘦𝘳𝘺?",url=QUERY_LINK)]
    ]
    return await callback_query.message.reply_voice(
        voice = DOWNLOAD_AUDIO,
        caption = f"**GREAT NEWS!! \n>You Can Now Share And Download Content With Unlimited Access For Your Chosen Duration. Just Pick A Plan Based On How Long You Need Access \n CHOOSE YOUR PLAN TYPE:**", 
        reply_markup=InlineKeyboardMarkup(btn), 
        disable_notification=True
        )

@Client.on_callback_query(filters.regex("payment"))
async def payment(client:Client, callback_query:CallbackQuery):
    data = callback_query.data.strip()
    subs_type = data.split("|")[1]
    user_id = callback_query.from_user.id
    plan = data.split("|")[-1]
    global OWNER_WARNING
    
    if subs_type == "access_token":
        amount = ACCESS_TOKEN_PLAN_1_PRICE if plan == "plan1" else ACCESS_TOKEN_PLAN_2_PRICE
    else:
        amount = DOWNLOAD_PLAN_1_PRICE if plan == "plan1" else DOWNLOAD_PLAN_2_PRICE
    
    result = await create_order(amount, user_id, subs_type, plan,username=client.me.username, message_id=callback_query.message.id)

    if not result['created']:
        await callback_query.answer(f"{result['message']} \n\n RETRY AFTER {get_readable_time(result['retry_after_seconds'])}", show_alert=True)
        if result['err_code'] in ('ERR03', 'ERR04') and OWNER_WARNING <=2:
            await client.send_message(
                chat_id=OWNER_ID[0],
                text=f"ORDER FAILED FOR {user_id} \n\n {result['message']} \n\n {'payment gateway subscription expired' if result['err_code']=='ERR03' else 'payment gateway cookies expired'} \n\n Check if cookies has been expired or not.\n\n After fixing the error click on done button \n\n Note:- If you don't click on done button then maybe you will not notified when the cookies will be expire",
                reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text = "Done", callback_data = "error_fixed_done")]]
                )
            )
            OWNER_WARNING += 1
        return
    
    order_id = result['order_id']
    btn =[
        [
            InlineKeyboardButton(
                text="Pay here", 
                url=result['pay_url']
                )
        ],
        [
            InlineKeyboardButton(
                text="Refresh",
                callback_data=f"refresh|{order_id}"
            ),
            InlineKeyboardButton(
                text="𝘏𝘦𝘭𝘱 & 𝘚𝘶𝘱𝘱𝘰𝘳𝘵",
                url=PAYMENT_QUERY
            )
        ]
    ]
    return await callback_query.edit_message_text(
        text=SUBS_3.format(order_id, amount),
        reply_markup=InlineKeyboardMarkup(btn)
    )

async def auto_delete_messages(client, snt_msgs, temp_msg, file, bot_username, delay):
    """Handle auto-deletion of messages without blocking the main handler"""
    try:
        await asyncio.sleep(delay)
        for snt_msg in snt_msgs:
            try:
                await snt_msg.delete()
            except MessageIdInvalid:
                pass
            except Exception as e:
                LOGGER(__name__).info(f"Error deleting message: {e}")
        
        try:
            start_param = file['_id']
            btn = [
                [
                    InlineKeyboardButton(
                        text="𝘞𝘢𝘵𝘤𝘩 𝘈𝘨𝘢𝘪𝘯 ", 
                        url=f"https://telegram.me/{bot_username}?start={start_param}" 
                    )
                ]
            ]
            await temp_msg.edit_text(text=AFTER_DELETE_TEXT.format(file['episode']), reply_markup=InlineKeyboardMarkup(btn))
        except MessageIdInvalid:
            pass
        except InputUserDeactivated:
            pass
        except Exception as e:
            LOGGER(__name__).info(f"Error updating temp message: {e}")
    except Exception as e:
        LOGGER(__name__).info(f"Error in auto_delete_messages: {e}")

@Client.on_callback_query(filters.regex("error_fixed_done"))
async def owner_warning_reset(client:Client, callback_query:CallbackQuery):
    """Reset the warning message send to owner"""
    global OWNER_WARNING
    OWNER_WARNING = 0
    return await callback_query.answer(text="Ok")

@Client.on_callback_query(filters.regex("shortner_error"))
async def shortner_error(client:Client, callback_query:CallbackQuery):
    return await callback_query.answer(text="Ads website is down for maintaince, Sorry for inconvenience!!!")

@Client.on_callback_query(filters.regex("POST_REACTION"))
async def reaction_callback(client: Client, callback_query: CallbackQuery):
    query_data = callback_query.data.split("|")
    user_id = callback_query.from_user.id
    
    post_id = query_data[1]
    emoji_key = query_data[2]
    updated_post = await add_post_reaction(post_id, emoji_key, user_id)
    updated_reactions = updated_post['reactions']
    
    if updated_reactions:
        btn = reaction_button(updated_reactions, post_id)
        asyncio.create_task(trigger_reaction_post_update(date_str=updated_post['date_str']))
        try:
            await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass
    else:
        await callback_query.answer("Post not found!", show_alert=True)
    
@Client.on_callback_query(filters.regex("refresh"))
async def refresh_payment(client:Client, callback_query:CallbackQuery):
    query_data = callback_query.data.split("|")
    user_id = callback_query.from_user.id
    order_id = query_data[1]
    result = await get_payment_details(order_id)
    user = await get_user(user_id)

    if result["activated"]:
        return await callback_query.edit_message_text(text="** YOUR TOKEN IS NOT VALID \n<pre>• Meybee Your Token Already Used By SomeOne</pre>\n<pre>•Maybe Your Token Could Be Wrong Too.</pre><pre>•Maybe You're Redeeming Someone Else's Token</pre>**", show_alert=True)

    if result['status'] == 'created':
        return await callback_query.answer(text="Payment not done yet!!! Retry again", show_alert=True)
    
    subs_type = result['subscription_type']
    plan = result['plan_type']

    if result['status'] in ['expired', 'cancelled']:
        await callback_query.message.delete()
        
        btn = [
        [
            InlineKeyboardButton(text="𝘛𝘳𝘺 𝘈𝘨𝘢𝘪𝘯", callback_data=f"payment|{subs_type}|{plan}"),
            InlineKeyboardButton(text="𝘏𝘦𝘭𝘱 𝘋𝘦𝘴𝘬", url=PAYMENT_HELP)
        ]
    ]
        return await client.send_video(
        chat_id=user_id,
        video="https://envs.sh/n1W.mp4",
        thumb=PAYMENT_THUMBNAIL,
        caption = ">**ITS LOOKS LIKE YOUR PAYMENT IS STILL PENDING...\n  If You're Experiencing Any Issues, You Can\n Follow The Tutorial Above Or Contact The \nHelp Desk To Get In Touch With An Admin\nFor Support.\n\n>If The ACTIVATE Button Isn't Visible After Payment, It May Be Because The Payment Was Made More Than 5 Minutes After Receiving The QR Code. The BOT Can't Provide The Button If The Payment Is Delayed.\n Send The ORDER ID (ORDERXXXX) To The \n TERABOX BOT To Activate It**",
        reply_markup=InlineKeyboardMarkup(btn), disable_notification=True
        )
    
    if result['status'] == 'paid':
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)
        if subs_type == "access_token":
            if plan == "plan1":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_1 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_1
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN1
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_1)
                await add_subscription('access', Plan.PLAN1, 'payment', user_id)
            elif plan == "plan2":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_2 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_2
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN2
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_2)
                await add_subscription('access', Plan.PLAN2, 'payment', user_id)
            user['access_token_type'] = Subs_Type.TYPE2
            await callback_query.message.reply_sticker("CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE", disable_notification=True)
            await callback_query.message.reply(
                text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                disable_notification=True
                )
        elif subs_type == "download":
            if plan == "plan1":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_1 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_1
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN1
                expiry = get_readable_time(DOWNLOAD_PLAN_1)
                await add_subscription('download',Plan.PLAN1, 'payment' ,user_id)
            elif plan == "plan2":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_2 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_2
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN2
                expiry = get_readable_time(DOWNLOAD_PLAN_2)
                await add_subscription('download',Plan.PLAN2, 'payment', user_id)
            
            user['access_download_type'] = Subs_Type.TYPE2
            await callback_query.message.reply_sticker("CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE")
            await callback_query.message.reply(
                text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                disable_notification=True
                )
            
        await update_order(order_id, "activated", True)
        await update_user(user_id, user)
        await callback_query.message.delete()
    
    else:
        return await callback_query.answer(text="Something went wrong!!!")


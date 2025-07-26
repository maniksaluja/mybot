import re
import pytz
import random
import asyncio
import datetime
from typing import List, Optional, Dict

from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ListenerTimeout
from pyrogram.types import  Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
from pyrogram.enums import ListenerTypes

from strings import LINK_GEN
from Stranger import LOGGER
from Stranger import app, userbot
from Stranger.misc import SUDOERS
from Stranger.utils.state import broadcast_state
from config import THUMBNAIL_PIC_1, THUMBNAIL_PIC_2, LOGS_CHANNEL_1, LOGS_CHANNEL_2
from Stranger.utils.database.mongodatabase import add_content, check_daily_prompt_needed, get_AG_settings, episode_counter, get_settings, mark_daily_prompt_sent, add_post
from Stranger.utils.helper import generate_unique_file_id, get_media_data, get_message_id, get_approximate_time, retry_with_flood_wait, thumb_link
from Stranger.plugins.tools.reaction_post import (
    create_today_reaction_post,
    trigger_reaction_post_update,
)

# Add episode counting
# Constants
BATCH_SIZE = 10
SLEEP_DELAY = 0.5
TIMEOUT_SECONDS = 60


class BatchProcessor:
    def __init__(self):
        self.processes: Dict[int, List[Message]] = {}
        self._status:str = "free"
        self.DIVIDER = "---BATCH_DIVIDER---"
    
    def start_process(self, user_id: int) -> bool:
        if user_id in self.processes:
            return False
        self.processes[user_id] = []
        self._status = "started"

        return True
    
    def is_batch(self,user_id: int) -> bool:
        return user_id in self.processes
    
    def add_divider(self, user_id: int) -> bool:
        """Add a divider between message groups"""
        if user_id not in self.processes:
            return False
        self.processes[user_id].append(self.DIVIDER)
        return True

    def cancel_process(self, user_id: int) -> bool:
        exists = user_id in self.processes
        self.processes.pop(user_id, None)
        self._status = "free"
        return exists
    
    def add_message(self, user_id: int, message: Message) -> bool:
        if user_id not in self.processes:
            return False
        self.processes[user_id].append(message)
        return True
    
    
    def get_message_groups(self, user_id: int) -> List[List[Message]]:
        """Get messages split into groups by dividers"""
        if user_id not in self.processes:
            return []
        groups = []
        current_group = []
        
        for item in self.processes[user_id]:
            if item == self.DIVIDER:
                if current_group:
                    groups.append(current_group)
                    current_group = []
            else:
                current_group.append(item)
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def status(self):
        return self._status

batch_processor = BatchProcessor()

async def send_file_to_userbot(message: Message, caption: str = None):
    """Helper function to send file to userbot using file_id method"""
    media_data = get_media_data(message)
    
    try:
        await app.send_cached_media(
            chat_id=userbot.one.id, 
            file_id=media_data['file_id'],
            caption=caption
        )
        return
    except PeerIdInvalid:
        try:
            await userbot.one.start_bot(chat_id=app.username)
            await app.send_cached_media(
                chat_id=userbot.one.id, 
                file_id=media_data['file_id'],
                caption=caption
            )
            return True
        except Exception as e:
            LOGGER(__name__).error(f"Error after start_bot: {e}")
            raise
    except Exception as e:
        LOGGER(__name__).error(f"Error in send_file_to_userbot: {e}")
        raise

@app.on_message(filters.command("cancel") & filters.private & SUDOERS)
async def cancel_batch(client: Client, message: Message):
    """**Cancel Ongoing Batch Process**"""
    if batch_processor.cancel_process(message.from_user.id):
        await message.reply("**Batch Process Cancelled**", disable_notification=True)
    else:
        await message.reply("**There Is Nothing to Cancel.**", disable_notification=True)


@app.on_message(
        SUDOERS 
        & filters.private 
        & ~filters.text,
        group=1,
        )
async def watcher(client: Client, message: Message):
    """Watch for media messages and generate links"""
    if message and message.text and message.text.startswith("/"):
        return
    if broadcast_state.is_broadcasting:
        broadcast_state.add_message(message)
        return
    if batch_processor.status() == "running":
        return await message.reply("**Batch Process Is Running.**", disable_notification=True)

    if message.from_user.id in batch_processor.processes:
        batch_processor.add_message(message.from_user.id, message)
        return
    
    data = await get_settings()

    bots = app.managed_bots
    bot_list = list(bots.keys())
    if len(bot_list) == 0:
        return await message.reply(">**No Bot Is Configured In The DataBase. Using /bot Command.**", disable_notification=True)
    bot = random.choice(bot_list)

    bot_username = bots[bot]['username']
    
    try:
        
        log_channels = []
        if data['logs']:
            if data['logs_type'] == 'logs1':
                log_channels.append(LOGS_CHANNEL_1)
            
            if data['logs_type'] == 'logs2':
                log_channels.append(LOGS_CHANNEL_2)

            if data['logs_type'] == 'both':
                log_channels.append(LOGS_CHANNEL_1)
                log_channels.append(LOGS_CHANNEL_2)

        media_data = get_media_data(message)

        if not media_data: 
            return await message.reply("**Not appropiate media type**", disable_notification=True)

        if message.video:
            dur = f"≼::≽ {get_approximate_time(message.video.duration)}"
        else:
            dur = ""

        ep = await episode_counter.increment_episode()
        cap = message.caption if message.caption else ""
        content_id = generate_unique_file_id(length=16)
        link = f'https://t.me/{bot_username}?start={content_id}'

        if cap:
            caption = f"Episode: {ep}\ncontent_id={content_id}\ncontent_index=PLACEHOLDER\n\n{cap}"
        else:
            caption = f"Episode: {ep}\ncontent_id={content_id}\ncontent_index=PLACEHOLDER"

        await add_content(content_id, ep)
        await send_file_to_userbot(message, caption)
        
        pic = None
        
        if data['thumbnail']:
            if data['thumbnail_type'] == 'type1':
                pic = THUMBNAIL_PIC_1
            elif data['thumbnail_type'] == 'auto':
                try:
                    if media_data['thumbnail']:
                        thumbnail_file = await app.download_media(
                            media_data['thumbnail'],
                            block=True,
                            in_memory=True
                        )
                        if thumbnail_file:
                            pic = thumbnail_file
                        else:
                            pic = THUMBNAIL_PIC_1
                    else:
                        pic = THUMBNAIL_PIC_1
                except Exception as e:
                    LOGGER(__name__).error(f"Error downloading thumbnail: {e}")
                    pic = THUMBNAIL_PIC_1
            else:
                pic = THUMBNAIL_PIC_2

        if pic:
            await retry_with_flood_wait(
                message.reply_photo,
                photo=pic,
                caption=LINK_GEN.format(cap, ep, dur, link),
                quote=True,
                disable_notification=True
                )
            if data['logs']:
                for log_channel in log_channels:
                    await retry_with_flood_wait(
                        app.send_photo,
                        chat_id=log_channel,
                        photo=pic,
                        caption=LINK_GEN.format(cap, ep, dur, link)
                        )
        else:
            await retry_with_flood_wait(
                message.reply, 
                text=LINK_GEN.format(cap, ep, dur, link),
                quote=True,
                disable_notification=True
                )
            if data['logs']:
                for log_channel in log_channels:
                    await retry_with_flood_wait(
                        app.send_message,
                        chat_id=log_channel,
                        text=LINK_GEN.format(cap, ep, dur, link)
                        )
    except Exception as e:
        LOGGER(__name__).error(f"Error in watcher: {e}")
        await message.reply(">**Error Generating Link**", quote=True, disable_notification=True)

@app.on_message(filters.command("batch") & filters.private & SUDOERS)
async def batch_link_gen(client: Client, message: Message):
    """Start batch link generation process"""
    if batch_processor.start_process(message.from_user.id) and len(list(app.managed_bots.keys())) > 0:
        await message.reply(
            "**OKAY Now I Can Make Batch Link**\n"
            "**When You Are Done Use** /makeit", 
            disable_notification=True
        )
    elif not (len(list(app.managed_bots.keys())) > 0):
        await message.reply(">**No Bots Available For Batch Link Generation \n>First Add Bots Using /bot**", disable_notification=True)
    else:
        await message.reply(
            "**Batch Process Already Running. Use /cancel To Cancel.**", 
            disable_notification=True
        )

@app.on_message(filters.command("makeit") & filters.private & SUDOERS)
async def make_batch_link(client: Client, message: Message):
    """Generate batch links for collected messages"""
    user_id = message.from_user.id
    if user_id not in batch_processor.processes:
        return await message.reply("**There Is No Batch Process Active**",disable_notification=True)
    
    if batch_processor._status == "running":
        return await message.reply("**Please Complete Previous Query**",disable_notification=True)
    
    messages = batch_processor.processes[user_id]
    if not messages:
        batch_processor.cancel_process(user_id)
        return await message.reply("**Before use /makeit cmand, Send Something For Creations**",disable_notification=True)
    
    if len(messages) < 2 :
        batch_processor.cancel_process(user_id)
        return await message.reply("**At-Least 2 Files Required For Batch Link Creation**",disable_notification=True)

    try:
        data = await get_settings()
        log_channels = []
        if data['logs']:
            if data['logs_type'] == 'logs1':
                log_channels.append(LOGS_CHANNEL_1)
            
            if data['logs_type'] == 'logs2':
                log_channels.append(LOGS_CHANNEL_2)

            if data['logs_type'] == 'both':
                log_channels.append(LOGS_CHANNEL_1)
                log_channels.append(LOGS_CHANNEL_2)

        bots = app.managed_bots
        bot_list = list(bots.keys())
        if len(bot_list) ==0:
            return await message.reply(">**No Bots Available For Generating Links. First Add Bot Using /bot Commmand**",disable_notification=True)
        
        bot = random.choice(bot_list)
        bot_username = bots[bot]['username']
        
        batch_processor._status = "running"
        temp = await message.reply("Batch Process Started",disable_notification=True)
        link, ep, dur, cap = await process_batch_messages(messages, user_id, bot_username)

        await temp.delete()
        dur_text = f"≼::≽ {get_approximate_time(dur)}" if dur else ""

        pic = None
        
        if data['thumbnail']:
            if data['thumbnail_type'] == 'type1':
                pic = THUMBNAIL_PIC_1
            elif data['thumbnail_type'] == 'auto':
                try:
                    thumbs = []
                    for msg in messages:
                        media_data = get_media_data(msg)
                        if media_data and media_data.get('thumbnail'):
                            thumbs.append(media_data['thumbnail'])
                    if thumbs:
                        tb = random.choice(thumbs)
                        thumbnail_file = await app.download_media(
                                tb,
                                block=True,
                                in_memory=True
                            )
                        if thumbnail_file:
                            pic = thumbnail_file
                        else:
                            pic = THUMBNAIL_PIC_1
                    else:
                        THUMBNAIL_PIC_1
                except Exception as e:
                    LOGGER(__name__).error(f"Error downloading thumbnail: {e}")
                    pic = THUMBNAIL_PIC_1
            else:
                pic = THUMBNAIL_PIC_2

        if pic:
            await retry_with_flood_wait(
                message.reply_photo,
                photo=pic,
                caption=LINK_GEN.format(cap, ep, dur_text, link),
                quote=True,
                disable_notification=True
                )
            if data['logs']:
                for log_channel in log_channels:
                    await retry_with_flood_wait(
                        app.send_photo,
                        chat_id=log_channel,
                        photo=pic,
                        caption=LINK_GEN.format(cap, ep, dur_text, link)
                        )
        else:
            await retry_with_flood_wait(
                message.reply, 
                text=LINK_GEN.format(cap, ep, dur_text, link),
                quote=True,
                disable_notification=True
                )
            if data['logs']:
                for log_channel in log_channels:
                    await retry_with_flood_wait(
                        app.send_message,
                        chat_id=log_channel,
                        text=LINK_GEN.format(cap, ep, dur_text, link)
                        )
    except Exception as e:
        LOGGER(__name__).error(f"Error in batch processing: {e}")
        await message.reply(f"Error: {str(e)}", quote=True, disable_notification=True)
    finally:
        batch_processor.cancel_process(user_id)

async def process_batch_messages(messages: List[Message], user_id:int, bot_username:str):
    """Process batch messages and generate link using file_id method"""
    ep = await episode_counter.increment_episode()
    content_id = generate_unique_file_id(length=16)
    dur = 0
    captions = []

    await add_content(content_id, ep)

    for message in messages:
        if not batch_processor.is_batch(user_id):
            break
        if not get_media_data(message):
            continue
        try:
            cap = message.caption if message.caption else ""
            if cap:
                captions.append(cap)
                caption = f"Episode: {ep}\ncontent_id={content_id}\ncontent_index=PLACEHOLDER\n\n{cap}"
            else:
                caption = f"Episode: {ep}\ncontent_id={content_id}\ncontent_index=PLACEHOLDER"

            dur += message.video.duration if message.video else 0
            
            await send_file_to_userbot(message, caption)
            
        except Exception as e:
            LOGGER(__name__).info(f"Error : {e}")
            pass
        await asyncio.sleep(SLEEP_DELAY)
    
    if captions:
        ret_cap = random.choice(captions)
    else:
        ret_cap = ""

    return f'https://t.me/{bot_username}?start={content_id}', ep, dur, ret_cap



@app.on_message(filters.command("promo") & filters.private & SUDOERS)
async def promo(client:Client, message:Message):
    btn = [
        [
            InlineKeyboardButton(text="𝖭𝖾𝗑𝗍 𝖲𝖾𝗍-𝗎𝗉 ", callback_data="promo_videos")
        ]
    ]
    if batch_processor.start_process(message.from_user.id) and len(list(app.managed_bots.keys())) > 0:
        return await message.reply(
            text="**•Now, Upload The File To Be Shown As A \n Preview Without Any Checks.\n\n •After The Previous Upload, Then Click\n On Next Setup To Upload Main Media.**", 
            reply_markup=InlineKeyboardMarkup(btn),
            disable_notification=True,
            quote=True,
            )
    elif len(list(app.managed_bots.keys())) == 0:
        return await message.reply(
            text=">**There Is No Bots Available To Process The PROMO Links. First Add Bots Using /bot [token]**",
            disable_notification=True,
            quote=True,
        )
    else:
        return await message.reply(
            "**Batch Process Already Running. Use /cancel To Cancel.**",
            disable_notification=True,
            quote=True,
        )

@app.on_callback_query(filters.regex("promo_videos") & SUDOERS)
async def promo_videos(client:Client, callback:CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    res = batch_processor.add_divider(user_id)
    if not res:
        return await callback.answer("No PromoLink Is Running", show_alert=True)
    
    btn = [
        [
            InlineKeyboardButton(text="𝖦𝖾𝗇𝖾𝗋𝖺𝗍𝖾 ", callback_data="done_promo")
        ]
    ]
    await callback.message.delete()
    await app.send_message(chat_id=chat_id, text="**•You Can Upload Main Media To Generate Link \n •When You're Uploading Done Click On Genrate Button**", reply_markup=InlineKeyboardMarkup(btn),disable_notification=True)

@app.on_callback_query(filters.regex("done_promo") & SUDOERS)
async def done_promo(client:Client, callback:CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    await callback.message.delete()

    if user_id not in batch_processor.processes:
        return await callback.answer("No Promo Is Activate", show_alert=True)
    
    if batch_processor._status == "running":
        return await callback.answer("Please Complete Previous Query")
    
    groups = batch_processor.get_message_groups(user_id)
    if not groups:
        batch_processor.cancel_process(user_id)
        return await callback.answer("No Messages To Process", show_alert=True)
    
    if len(groups) != 2:
        batch_processor.cancel_process(user_id)
        return await callback.answer("Invalid Number Of Messages", show_alert=True)
    
    for grp in groups:
        if not grp:
            batch_processor.cancel_process(user_id)
            return await callback.answer("No Promo Images Or Videos To Process", show_alert=True)
    
    data = await get_settings()
        
    bots = app.managed_bots
    if len(list(bots.keys())) == 0:
        return callback.answer(text=">**No Bots Found To Generate Links. First Add Bots Using /bot [token]**", show_alert=True)
    bot = random.choice(list(bots.keys()))
    bot_username = bots[bot]['username']
        
    batch_processor._status = "running"

    ep = await episode_counter.increment_episode()
    dur = 0

    captions = []
    thumbs = []

    temp = await app.send_message(chat_id=user_id ,text="Batch Process Started",disable_notification=True)

    second_group_content_id = None
    if len(groups) > 1:
        second_group_content_id = generate_unique_file_id(length=16)

    for x in range(len(groups)-1, -1, -1):
        current_content_id = second_group_content_id if x == 1 else generate_unique_file_id(length=16)
        current_promo_link = second_group_content_id if x == 0 else None

        await add_content(current_content_id, ep, promo_link=current_promo_link)

        current_group = groups[x]
        for msg in current_group:
            media_data = get_media_data(msg)
            if media_data and media_data.get('thumbnail'):
                thumbs.append(media_data['thumbnail'])
            cap = msg.caption if msg.caption else ""
            if cap:
                captions.append(cap)
                caption = f"Episode: {ep}\ncontent_id={current_content_id}\ncontent_index=PLACEHOLDER\n\n{cap}"
            else:
                caption = f"Episode: {ep}\ncontent_id={current_content_id}\ncontent_index=PLACEHOLDER"
            dur += msg.video.duration if msg.video else 0
            
            await send_file_to_userbot(msg, caption)
            await asyncio.sleep(0.2)

        if x == 0:
            link = current_content_id
    
    pic = None
    if data['thumbnail']:
        if data['thumbnail_type'] == 'type1':
            pic = THUMBNAIL_PIC_1
        elif data['thumbnail_type'] == 'auto':
            try:
                if thumbs:
                    tb = random.choice(thumbs)
                    thumbnail_file = await app.download_media(
                            tb,
                            block=True,
                            in_memory=True
                        )
                    if thumbnail_file:
                        pic = thumbnail_file
                    else:
                        pic = THUMBNAIL_PIC_1
                else:
                    THUMBNAIL_PIC_1
            except Exception as e:
                LOGGER(__name__).error(f"Error downloading thumbnail: {e}")
                pic = THUMBNAIL_PIC_1
        else:
            pic = THUMBNAIL_PIC_2

    log_channels = []
    if data['logs']:
        if data['logs_type'] == 'logs1':
            log_channels.append(LOGS_CHANNEL_1)
        
        if data['logs_type'] == 'logs2':
            log_channels.append(LOGS_CHANNEL_2)
        if data['logs_type'] == 'both':
            log_channels.append(LOGS_CHANNEL_1)
            log_channels.append(LOGS_CHANNEL_2)

    if captions:
        ret_cap = random.choices(captions)
    else:
        ret_cap = ""

    await temp.delete()
    dur_text = f"≼::≽ {get_approximate_time(dur)}" if dur else ""
    updated_link = f'https://t.me/{bot_username}?start=promo_{link}'
    if pic:
        await retry_with_flood_wait(
            app.send_photo,
            chat_id=chat_id,
            photo=pic,
            caption=LINK_GEN.format(ret_cap, ep, dur_text, updated_link)
            )
        if data['logs']:
            for log_channel in log_channels:
                await retry_with_flood_wait(
                    app.send_photo,
                    chat_id=log_channel,
                    photo=pic,
                    caption=LINK_GEN.format(ret_cap, ep, dur_text, updated_link)
                    )
    else:
        await retry_with_flood_wait(
            app.send_message, 
            chat_id=chat_id,
            text=LINK_GEN.format(ret_cap, ep, dur_text, updated_link)
            )
        if data['logs']:
            for log_channel in log_channels:
                await retry_with_flood_wait(
                    app.send_message,
                    chat_id=log_channel,
                    text=LINK_GEN.format(ret_cap, ep, dur_text, updated_link)
                    )
    batch_processor.cancel_process(user_id)


@app.on_message(filters.command("posting") & filters.private & SUDOERS)
async def set_links(client:Client,message:Message):
    user_id = message.from_user.id
    xx = await app.send_message(user_id, "Starting" , reply_markup=ReplyKeyboardRemove(),disable_notification=True)
    await xx.delete()
    if batch_processor.start_process(user_id):
        return await app.send_message( 
            chat_id=user_id,
            text ="**POST CREATION ACTIVATED\n> Now You Can Upload You're Posts \n>To Store In DataBase \n •Use /Done To Store In Posting DataBase \n •Use /cancel To Stop Prosesss.**"
        )
    else:
        return await app.send_message( 
            chat_id=user_id,
            text="Post Process Already Running. Use /cancel To Stop."
        )

@app.on_message(filters.command("done") & filters.private & SUDOERS)
async def done_post(client: Client, message: Message):
    """Handle done post command."""
    user_id = message.from_user.id
    if user_id not in batch_processor.processes:
        return await message.reply("No Post Process Active",disable_notification=True)
    
    if batch_processor._status == "running":
        return await message.reply("Please Complete Previous Query",disable_notification=True)
    
    messages = batch_processor.processes[user_id]
    if not messages:
        batch_processor.cancel_process(user_id)
        return await message.reply("**There Is No File To Upload**",disable_notification=True)
    
    batch_processor._status = "running"
    buttons = [
        [
            InlineKeyboardButton("𝖨𝗇𝖽𝗂𝖺𝗇", callback_data=f"SET_LINK | indian"),
            InlineKeyboardButton("𝖦𝗅𝗈𝖻𝖺𝗅", callback_data="SET_LINK | global")
        ],
        [
            InlineKeyboardButton("𝖣𝖺𝗋𝗄", callback_data="SET_LINK | dark"),
            InlineKeyboardButton("𝖮𝗍𝗁𝖾𝗋𝗌", callback_data="SET_LINK | others")
        ],
        ]
    await message.delete()
    return await app.send_message(
        user_id,
        text="**Choose Your Category**", 
        reply_markup = InlineKeyboardMarkup(buttons),
        disable_notification=True
        )

def extract_start_value(caption: str) -> str:
    """Extract the value after ?start= from a Telegram bot link in caption"""
    if not caption:
        return ""
    
    pattern = r'\?start=([A-Za-z0-9_-]+)'
    match = re.search(pattern, caption)
    
    if match:
        return match.group(1)
    return ""

@app.on_callback_query(filters.regex("SET_LINK") & SUDOERS)
async def set_links_callback(client: Client, callback_query: CallbackQuery):
    """Handle callback for setting links in different categories."""
    user_id = callback_query.from_user.id
    chat = callback_query.message.chat
    try:
        callback_data = callback_query.data.strip()
        category = str(callback_data.split("|")[-1].strip())
        
        await callback_query.message.delete()
        messages = batch_processor.processes[user_id]
        if not messages:
            batch_processor.cancel_process(user_id)
            return await app.send_message(chat_id= user_id,text="No Files Sent")
        temp_msg = await app.send_message(chat_id=user_id, text="Please Wait ....")

        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)

        for msg in messages:
            if msg.caption:
                caption = msg.caption
            elif msg.text:
                caption = msg.text
            else:
                caption = ""
            
            content_id = extract_start_value(caption)
            
            if not get_media_data(msg):
                LOGGER(__name__).warning(f"Skipping message without media: {msg.id}")
                await msg.reply("No media found. Skipping")
                continue

            try:
                file = await app.download_media(msg, in_memory=True)
                if not file:
                    LOGGER(__name__).error(f"Failed to download media for message: {msg.id}")
                    continue
                    
                thumblink = thumb_link(file)
                
                if not thumblink:
                    LOGGER(__name__).error(f"Failed to generate thumb link for message: {msg.id}")
                    continue

                await add_post(
                    category=category,
                    caption=caption,
                    thumblink=thumblink,
                    created_date=current_time,
                    content_id=content_id
                )
            except Exception as e:
                LOGGER(__name__).error(f"Error processing message {msg.id}: {e}")
                continue
            
            await asyncio.sleep(0.5)
        
        if await check_daily_prompt_needed(current_time):
            btn = [
                [InlineKeyboardButton("𝘠𝘦𝘴", callback_data="daily_post_yes")]
            ]
            snt_msg = await app.send_message(
                chat_id=user_id, 
                text="**Do You Want To Upload  New Post  For \nSHANAYA ALERT?? \n\n ≼WARING≽ \n> If Yes Is Selected, The Old Post Will Be Given-UP,\n> And The Focus Will Shift To The New Post.**",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_notification=True,
            )
            await snt_msg.pin(disable_notification=True, both_sides=True)
            await mark_daily_prompt_sent(current_time)
        else:    
            asyncio.create_task(trigger_reaction_post_update(force=True))

        await temp_msg.edit(text="**Your Posts Successfully Uploaded**")
    except Exception as e:
        LOGGER(__name__).info(f"Error : {e}")
        await callback_query.message.reply(f"❌ An error occurred: {str(e)}",disable_notification=True)
    finally:
        batch_processor.cancel_process(user_id)


@app.on_callback_query(filters.regex("daily_post_yes") & SUDOERS)
async def daily_post_yes_callback_handler(_, callback_query: CallbackQuery):
    """Handle daily post creation confirmation"""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.datetime.now(ist)
    
    await mark_daily_prompt_sent(current_time)
    
    await create_today_reaction_post()
    await callback_query.message.delete()

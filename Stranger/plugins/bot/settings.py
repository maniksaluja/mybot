import asyncio
from pyrogram import filters,Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ListenerTimeout
from Stranger import app
from Stranger.misc import SUDOERS
from Stranger.utils.inline import (
    setting_markup, 
    logs_panel_markup,
    thumbnail_panel_markup,
    access_token_setting_panel, 
    auto_approval_setting_panel,
    )
from Stranger.utils.database import (
    get_settings , 
    update_settings
    )

user_auto_delete_tasks = {}
user_related_messages = {}

def cancel_auto_delete_task(user_id):
    """Cancel existing auto-delete task for a user and clean up immediately"""
    if user_id in user_auto_delete_tasks:
        user_auto_delete_tasks[user_id].cancel()
        del user_auto_delete_tasks[user_id]
        if user_id in user_related_messages:
            del user_related_messages[user_id]

def schedule_auto_delete(user_id, messages, delay=300):
    """Schedule auto-delete for messages and cancel any existing task"""
    cancel_auto_delete_task(user_id)
    task = asyncio.create_task(auto_delete_messages_with_cleanup(user_id, messages, delay))
    user_auto_delete_tasks[user_id] = task

async def auto_delete_messages_with_cleanup(user_id, messages, delay=300):
    """Auto delete messages after specified delay and clean up tracking"""
    try:
        await asyncio.sleep(delay)
        for msg in messages:
            try:
                await msg.delete()
            except Exception:
                pass  
        
        if user_id in user_auto_delete_tasks:
            del user_auto_delete_tasks[user_id]
        if user_id in user_related_messages:
            del user_related_messages[user_id]
            
    except asyncio.CancelledError:
        pass

def reset_auto_delete_timer(func):
    """Decorator to reset auto-delete timer on user interaction"""
    async def wrapper(client, callback_query):
        user_id = callback_query.from_user.id
        cancel_auto_delete_task(user_id)  
        
        result = await func(client, callback_query)
        
        messages_to_delete = [callback_query.message]
        if user_id in user_related_messages:
            messages_to_delete.extend(user_related_messages[user_id])
        
        schedule_auto_delete(user_id, messages_to_delete, delay=300)
        
        return result
    return wrapper


@app.on_callback_query(filters.regex("dummy"))
async def dummy(_, cq: CallbackQuery):
    return await cq.answer()

@app.on_callback_query(filters.regex("close"))
async def close_panel(client:Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    cancel_auto_delete_task(user_id)
    
    if user_id in user_related_messages:
        for msg in user_related_messages[user_id]:
            try:
                await msg.delete()
            except Exception:
                pass
    
    await callback.message.delete()

@app.on_callback_query(filters.regex("settings_back_helper"))
@reset_auto_delete_timer
async def setting_cl_panel(client:Client,callback_query:CallbackQuery):
    data = await get_settings()
    buttons = setting_markup(data)
    
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("settings") &  filters.private & SUDOERS)
async def setting_panel(client:Client,message:Message):
    user_id = message.from_user.id
    
    data = await get_settings()
    buttons = setting_markup(data)
    
    sticker_msg = await message.reply_sticker("CAACAgUAAxkBAAEODJhnzwxv5It3B-zI0Mgxdd5G3MPJhQAC8RMAAm35cFVy4RqfkYqoNjYE", disable_notification=True)
    settings_msg = await message.reply_text(
        "**IT Helps To Change Bot Basic Settings.**" ,  
        reply_markup=InlineKeyboardMarkup(buttons), 
        disable_notification=True
        )
    
    user_related_messages[user_id] = [sticker_msg]
    
    schedule_auto_delete(user_id, [sticker_msg, settings_msg], delay=300)
    
    return settings_msg


@app.on_callback_query(filters.regex("auto_approval_toggle") & SUDOERS)
@reset_auto_delete_timer
async def auto_approval_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    ap = False if data['auto_approval'] else True
    await update_settings("auto_approval" ,ap)
    data['auto_approval'] = ap
    buttons = setting_markup(data)
    
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))
    
@app.on_callback_query(filters.regex("auto_approval_setting") & SUDOERS)
@reset_auto_delete_timer
async def auto_approval_setting(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    buttons = auto_approval_setting_panel(data)
    
    return await callback_query.edit_message_text("**Auto Approval Settings**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("ap_setting_toggle") & SUDOERS)
@reset_auto_delete_timer
async def ap_setting_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    q = callback_query.data.strip()
    query = str(q.split("|")[-1].strip())
    ap = False if data[query] else True
    await update_settings(query , ap)
    data[query] = ap
    buttons = auto_approval_setting_panel(data)
    return await callback_query.edit_message_text("**Auto Approval Settings**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("access_token_toggle") & SUDOERS)
@reset_auto_delete_timer
async def access_token_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    at = False if data['access_token'] else True
    await update_settings("access_token" , at)
    data['access_token'] = at
    buttons = setting_markup(data)
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("access_token_setting") & SUDOERS)
@reset_auto_delete_timer
async def access_token_setting(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    buttons = access_token_setting_panel(data)
    return await callback_query.edit_message_text("**Earning Settings**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("at_setting_toggle") & SUDOERS)
@reset_auto_delete_timer
async def at_setting_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    q = callback_query.data.strip()
    query = str(q.split("|")[-1].strip())
    ap = False if data[query] else True
    await update_settings(query , ap)
    data[query] = ap
    buttons = access_token_setting_panel(data)
    return await callback_query.edit_message_text("**Eanring Settings**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("thumbnail_toggle") & SUDOERS)
@reset_auto_delete_timer
async def thumbnail_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    th = False if data['thumbnail'] else True
    await update_settings("thumbnail" , th)
    data['thumbnail'] = th
    buttons = setting_markup(data)
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("thumbnail_panel") & SUDOERS)
@reset_auto_delete_timer
async def thumbnail_panel(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    buttons = thumbnail_panel_markup(data['thumbnail_type'])
    return await callback_query.edit_message_text("**Now You Can Choose Thumbnail **", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("thumbnail_type") & SUDOERS)
@reset_auto_delete_timer
async def thumbnail_type(client: Client, callback_query: CallbackQuery):
    q = callback_query.data.strip()
    query = str(q.split("|")[-1].strip())
    await update_settings("thumbnail_type", str(query))
    buttons = thumbnail_panel_markup(query)
    try:
        return await callback_query.edit_message_text("**Now You Can Choose Thumbnail **", reply_markup=InlineKeyboardMarkup(buttons))
    except:
        return


@app.on_callback_query(filters.regex("logs_channel_toggle") & SUDOERS)
@reset_auto_delete_timer
async def logs_channel_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    logs = False if data['logs'] else True  
    await update_settings("logs" , logs)
    data['logs'] = logs
    buttons = setting_markup(data)
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("logs_panel") & SUDOERS)
@reset_auto_delete_timer
async def logs_panel(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    buttons = logs_panel_markup(data['logs_type'])
    return await callback_query.edit_message_text("**Choose Your LOG Channel**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("logs_setting_toggle"))
@reset_auto_delete_timer
async def logs_setting_toggle(client: Client, callback_query: CallbackQuery):
    q = callback_query.data.strip()
    query = str(q.split("|")[-1].strip())
    await update_settings("logs_type", str(query))
    buttons = logs_panel_markup(query)
    return await callback_query.edit_message_text("**Choose Your LOG Channel**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("promotion_toggle"))
@reset_auto_delete_timer
async def promotion_toggle(client: Client, callback_query: CallbackQuery):
    data = await get_settings()
    promotion = False if data['promotion'] else True
    await update_settings("promotion", promotion)
    data['promotion'] = promotion
    buttons = setting_markup(data)
    return await callback_query.edit_message_text("**IT Helps To Change Bot Basic Settings.**" ,  reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("set_promotion"))
@reset_auto_delete_timer
async def set_promotion(client: Client, callback_query: CallbackQuery):
    chat = callback_query.message.chat
    user_id = callback_query.from_user.id
    await callback_query.message.delete()

    try:
        msg:Message = await chat.ask(
            "Now send the promotional message",
            timeout=60,
        )
    except ListenerTimeout:
        await app.send_message(
            chat_id=user_id,
            text="**TimeOut: No Response Received**" ,
            disable_notification=True
            )
        return
    except Exception as e:
        await app.send_message(f"Error occurred: {str(e)}" ,disable_notification=True)
        return

    if msg:
        await msg.sent_message.delete()

        ad_media = []

        if msg.media_group_id:
            mess = msg.get_media_group()
            for m in mess:
                m:Message
                if m.photo:
                    ad_media.append({
                        "type": "photo",
                        "file_id": m.photo.file_id,
                        "caption": m.caption if m.caption else ""
                    })
                elif m.video:
                    ad_media.append({
                        "type": "video",
                        "file_id": m.video.file_id,
                        "caption": m.caption if m.caption else ""
                    })
                elif m.document:
                    ad_media.append({
                        "type": "document",
                        "file_id": m.document.file_id,
                        "caption": m.caption if m.caption else ""
                    })
                elif m.audio:
                    ad_media.append({
                        "type": "audio",
                        "file_id": m.audio.file_id,
                        "caption": m.caption if m.caption else ""
                    })
                elif m.sticker:
                    ad_media.append({
                        "type": "sticker",
                        "file_id": m.sticker.file_id,
                        "caption": m.caption if m.caption else ""
                    })
                elif m.voice:
                    ad_media.append({
                        "type": "voice",
                        "file_id": m.voice.file_id,
                        "caption": m.caption if m.caption else ""
                    })
        elif msg.photo:
            ad_media.append({
                "type":"photo",
                "file_id":msg.photo.file_id,
                "caption":msg.caption if msg.caption else ""
            })
        elif msg.video:
            ad_media.append({
                "type":"video",
                "file_id":msg.video.file_id,
                "caption":msg.caption if msg.caption else ""
            })
        elif msg.document:
            ad_media.append({
                "type": "document",
                "file_id": msg.document.file_id,
                "caption": msg.caption if msg.caption else ""
            })
        elif msg.audio:
            ad_media.append({
                "type": "audio",
                "file_id": msg.audio.file_id,
                "caption": msg.caption if msg.caption else ""
            })
        elif msg.sticker:
            ad_media.append({
                "type": "sticker",
                "file_id": msg.sticker.file_id,
            })
        elif msg.voice:
            ad_media.append({
                "type": "voice",
                "file_id": msg.voice.file_id,
            })
        else:
            ad_media.append({
                "type": "text",
                "caption": msg.text
            })

        await update_settings("promotion_data", ad_media)

        return await app.send_message(
            chat_id=user_id,
            text="Promotional message has been set"
        )
    
    return await app.send_message(
        chat_id=user_id,
        text="Invalid media/text",
    )


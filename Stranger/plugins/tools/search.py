import asyncio
import re
import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from Stranger.misc import SUDOERS
from Stranger.utils.database.mongodatabase import search_channel_files, get_content
from Stranger import app, LOGGER
from Stranger.utils.helper import get_readable_time, retry_with_flood_wait
from Stranger.utils.search_pagination import (
    store_search_results, 
    get_paginated_results, 
    update_page, 
    clean_expired_sessions,
    has_active_session
)
from config import AUTO_DELETE_POST, BANNED_USERS
from strings import CONTENT_WAIT_STICKER, CONTENT_NOT_FOUND_STICKER


MESSAGE_DELAY = 1.5  # seconds

pending_find: Dict[int, datetime] = {}
# Store sent messages for auto-deletion
sent_messages_store: Dict[int, list] = {}
pagination_messages: Dict[int, Message] = {}

async def send_paginated_results(client, user_id, pagination_data, message_to_edit=None):
    """Send or edit message with paginated search results"""
    if not pagination_data or not pagination_data["results"]:
        return None
    
    results = pagination_data["results"]
    current_page = pagination_data["current_page"]
    total_pages = pagination_data["total_pages"]
    total_results = pagination_data["total_results"]
    
    # Create pagination buttons
    buttons = []
    
    # Add navigation buttons
    nav_buttons = []
    if pagination_data["has_prev"]:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data="search_prev"))
    
    # Add page indicator
    nav_buttons.append(InlineKeyboardButton(
        f"📄 {current_page}/{total_pages}", 
        callback_data="search_page"
    ))
    
    if pagination_data["has_next"]:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data="search_next"))
    
    buttons.append(nav_buttons)
    
    # Add refresh button
    buttons.append([
        InlineKeyboardButton("🔄 Refresh Search", callback_data="search_refresh")
    ])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    # Send or edit message with current page info
    text = (
        f"**Search Results for:** `{pagination_data['query']}`\n"
        f"Found {total_results} results | Page {current_page} of {total_pages}\n\n"
        f"Showing {len(results)} results for this page."
    )
    
    # Add auto-deletion info if enabled
    if AUTO_DELETE_POST:
        text += f"**\n\n>Messages Will Be Deleted After {get_readable_time(AUTO_DELETE_POST)}**"
    
    if message_to_edit:
        try:
            return await message_to_edit.edit_text(text, reply_markup=keyboard)
        except Exception as e:
            # If edit fails, send a new message
            LOGGER(__name__).info(f"Error editing pagination message: {e}")
            return await client.send_message(
                user_id, 
                text,
                reply_markup=keyboard,
                disable_notification=True
            )
    else:
        return await client.send_message(
            user_id, 
            text,
            reply_markup=keyboard,
            disable_notification=True
        )

async def send_search_results(client, user_id, pagination_data, is_navigation=False):
    """Send search results with proper message ordering and cleanup"""
    if not pagination_data or not pagination_data["results"]:
        return []
    
    # Get content from database
    sent_msgs = []
    bots = app.managed_bots
    bot = random.choice(list(bots.keys()))
    bot_username = bots[bot]['username']
    
    # Clear any existing pagination message if this is navigation
    if is_navigation and user_id in pagination_messages:
        try:
            await pagination_messages[user_id].delete()
        except Exception:
            pass
        pagination_messages.pop(user_id, None)
    
    # Send content messages first - Updated for new posts structure
    for doc in pagination_data["results"]:
        try:
            # Extract bot link from caption to get start parameter
            caption = doc.get('caption', '')
            bot_link_pattern = r'https://(?:t(?:elegram)?\.me)/([^/\s?]+)\?start=([^\s]+)'
            match = re.search(bot_link_pattern, caption)
            
            if match:
                start_param = match.group(2)
                # Create new bot link with current bot username
                new_link = f"https://telegram.me/{bot_username}?start={start_param}"
                # Replace old link with new one in caption
                new_caption = caption.replace(match.group(0), new_link)
                
                # Create message content
                message_text = new_caption
                
                # Add post metadata for context
                if doc.get('total_reactions', 0) > 0:
                    message_text += f"\n\n👥 Reactions: {doc['total_reactions']}"
                
                btn = None
                if user_id in SUDOERS:
                    btn = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                            text="🗑️ DELETE POST",
                                callback_data=f"DELETE_POST|{doc['post_id']}"
                            )
                            ]
                    ])


                # Send as text message with thumbnail if available
                if doc.get('thumblink'):
                    try:
                        sent_msg = await client.send_photo(
                            chat_id=user_id,
                            photo=doc['thumblink'],
                            caption=message_text,
                            disable_notification=True,
                            reply_markup=btn
                        )
                    except Exception:
                        # Fallback to text message if photo fails
                        sent_msg = await client.send_message(
                            chat_id=user_id,
                            text=message_text,
                            disable_web_page_preview=False,
                            disable_notification=True,
                            reply_markup=btn
                        )
                else:
                    sent_msg = await client.send_message(
                        chat_id=user_id,
                        text=message_text,
                        disable_web_page_preview=False,
                        disable_notification=True,
                        reply_markup=btn
                    )
                
                sent_msgs.append(sent_msg)
                await asyncio.sleep(MESSAGE_DELAY)
            else:
                # If no bot link found, send caption as is
                sent_msg = await client.send_message(
                    chat_id=user_id,
                    text=caption or "No caption available",
                    disable_web_page_preview=False,
                    disable_notification=True
                )
                sent_msgs.append(sent_msg)
                await asyncio.sleep(MESSAGE_DELAY)
                
        except Exception as e:
            LOGGER(__name__).info(f"Error sending message: {e}")
    
    # Now send pagination message after content
    pagination_msg = await send_paginated_results(client, user_id, pagination_data)
    pagination_messages[user_id] = pagination_msg
    
    # Store messages for auto-deletion
    if AUTO_DELETE_POST:
        # Add pagination message to auto-delete list too
        sent_msgs.append(pagination_msg)
        
        # Update user's sent messages store
        if user_id not in sent_messages_store:
            sent_messages_store[user_id] = []
        
        sent_messages_store[user_id].extend(sent_msgs)
        
        # Schedule auto-deletion
        asyncio.create_task(auto_delete_messages(user_id, sent_msgs))
    
    return sent_msgs

async def auto_delete_messages(user_id, messages, delay=None):
    """Auto-delete messages after specified delay"""
    if not delay:
        delay = AUTO_DELETE_POST
    
    if not delay or not messages:
        return
    
    await asyncio.sleep(delay)
    
    # Delete messages
    for msg in messages:
        try:
            await msg.delete()
        except Exception:
            pass
    
    # Remove from storage
    if user_id in sent_messages_store:
        sent_messages_store[user_id] = [
            msg for msg in sent_messages_store[user_id] 
            if msg not in messages
        ]

@app.on_message(filters.command("find") & ~BANNED_USERS)
async def find(client: Client, message: Message):
    if len(message.command) < 2:
        btn = [
            [
                InlineKeyboardButton(text="𝘏𝘰𝘸 𝘛𝘰 𝘧𝘪𝘯𝘥 𝘊𝘰𝘯𝘵𝘦𝘯𝘵", url = "https://t.me/Ultra_XYZ/14")
            ]
        ]
        return await message.reply_text(">**Please Provide a Search Query!**",disable_notification=True,  reply_markup=InlineKeyboardMarkup(btn))

    await message.delete()
    
    user_id = message.from_user.id
    current_time = datetime.now()

    # Clean expired sessions periodically
    clean_expired_sessions()

    if user_id in pending_find:
        last_request = pending_find[user_id]
        if (current_time - last_request) > timedelta(seconds=60):
            del pending_find[user_id]
        else:
            return await message.reply_text(">**You Are Already In The Queue. Please Wait For The Previous Query To Finish**",disable_notification=True)
    
    pending_find[user_id] = current_time

    query = message.text.split(None, 1)[1]
    
    if len(list(app.managed_bots.keys())) == 0:
        if user_id in pending_find:
                del pending_find[user_id]
        return await message.reply("**SOMTHING WENT WRONG\n Contact To Admin To Fix This Problem**")
    
    bots = app.managed_bots
    bot = random.choice(list(bots.keys()))
    bot_username = bots[bot]['username']

    temp_sticker = await message.reply_sticker(CONTENT_WAIT_STICKER,disable_notification=True)

    bot_link_pattern = r'https://(?:t(?:elegram)?\.me)/([^/\s?]+)\?start=([^\s]+)'
    match = re.search(bot_link_pattern, query)
    if match:
        start_param = match.group(2)
        result = await get_content(start_param)

        if not result:
            if user_id in pending_find:
                del pending_find[user_id]
            await temp_sticker.delete()
            return await message.reply_sticker("CAACAgUAAxkBAAEN345nuV3aFIZ0_z18xjAFfJIegVRAAgACXxMAAmAkeVXgbAPgeJeGyzYE",disable_notification=True)
        
        new_link = f"https://telegram.me/{bot_username}?start={start_param}"

        await message.reply_text(f"Here is the new link \n\n {new_link}",disable_notification=True)
        if user_id in pending_find:
            del pending_find[user_id]
        return await temp_sticker.delete()
    
    try:
        results = await search_channel_files(query)
        
        if not results:
            await temp_sticker.delete()
            await message.reply_sticker(CONTENT_NOT_FOUND_STICKER, disable_notification=True)
            btn = [
                [
                    InlineKeyboardButton(text="𝘔𝘢𝘬𝘦 𝘈 𝘙𝘦𝘲𝘶𝘦𝘴𝘵", callback_data="important_start")
                ]
            ]
            if user_id in pending_find:
                del pending_find[user_id]
            return await message.reply_text(
                text="**No Results Found for Your Query**\n\nTry using different keywords or check spelling." , 
                reply_markup=InlineKeyboardMarkup(btn),
                disable_notification=True
                )
        
        await message.delete()
        # Store search results for pagination
        store_search_results(user_id, results, query)
        
        # Get first page of results
        pagination_data = get_paginated_results(user_id)
        
        # Send content messages followed by pagination info
        await send_search_results(client, user_id, pagination_data)
        
        # Clean up temporary messages
        await temp_sticker.delete()
    
    except Exception as e:
        LOGGER(__name__).error(f"Error in search: {e}")
        await temp_sticker.delete()
        await message.reply_text("**Search Error Occurred**\n\nPlease try again with different keywords.", disable_notification=True)
    finally:
        if user_id in pending_find:
            del pending_find[user_id]

@app.on_callback_query(filters.regex("^search_(next|prev|refresh|page)$"))
async def handle_search_pagination(client: Client, callback_query: CallbackQuery):
    """Handle search pagination callbacks"""
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]

    # Clean expired sessions periodically
    clean_expired_sessions()
    
    # Check if user has active search session
    if not has_active_session(user_id):
        return await callback_query.answer("Search Session Expired. Please Search Sgain.", show_alert=True)
    
    # Clean any pending find operations
    if user_id in pending_find:
        del pending_find[user_id]
    
    if action == "page":
        # Just show current page info
        return await callback_query.answer(f"Current Page", show_alert=False)
    
    await callback_query.answer("Loading Results...")
    
    if action == "refresh":
        # Refresh current page
        pagination_data = get_paginated_results(user_id)
    else:
        # Navigate to next/prev page
        pagination_data = update_page(user_id, action)
    
    if not pagination_data:
        return await callback_query.answer("No More Results Or Session Expired", show_alert=True)
    
    # Clear existing pagination message temporarily to indicate loading
    if user_id in pagination_messages:
        try:
            await pagination_messages[user_id].edit_text(
                "Loading New Page, Please Wait..."
            )
        except Exception:
            pass
    
    # Send new content with pagination message
    await send_search_results(client, user_id, pagination_data, is_navigation=True)


import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from config import BOT_TOKEN
from Stranger.utils.helper import get_media_data
from Stranger import userbot, app, LOGGER
from Stranger.utils.database.mongodatabase import (
    add_content, 
    add_userbot_one_data, 
    content_exists,
)
from Stranger.utils.file_manager import file_manager


MAIN_BOT_ID = int(BOT_TOKEN.split(":")[0])

@Client.on_message(filters.incoming & filters.media & filters.chat(MAIN_BOT_ID))
async def listener(client:Client, message:Message):
    media_data = get_media_data(message)

    if not media_data:
        return
    
    caption = message.caption
    if not caption:
        return
    
    # Extract content_id using regex
    content_match = re.search(r'content_id=([^\s\n]+)', caption)
    episode_match = re.search(r'Episode: (\d+)', caption)

    if not content_match:
        return
    
    content_id = content_match.group(1)
    episode = int(episode_match.group(1)) if episode_match else 1
    
    # Create content entry if it doesn't exist
    if not await content_exists(content_id):
        await add_content(content_id, episode)

    # Save to userbot.one (original method)
    saved_msg = await userbot.one.send_cached_media(
        chat_id="me",
        file_id=media_data['file_id'],
        caption=caption
    )

    saved_media_data = get_media_data(saved_msg)
    
    # Add userbot_one_data to MongoDB
    success, content_index = await add_userbot_one_data(
        content_id=content_id,
        file_id=saved_media_data['file_id'],
        media_type=saved_media_data['type'],
        caption=caption,
        msg_id=saved_msg.id,
        user_id=userbot.one.me.id
    )
    
    if not success:
        LOGGER(__name__).error(f"Failed to add userbot_one_data for content_id: {content_id}")
        return
    
    # Process file with new file manager (download and upload to userbot.two)
    asyncio.create_task(file_manager.process_file(message, content_id, content_index))
    
    # Update caption with content_index
    updated_caption = caption.replace("content_index=PLACEHOLDER", f"content_index={content_index}")

    # Send to managed bots
    for bot_token, bot_info in app.managed_bots.items():
        try:
            await userbot.one.send_cached_media(
                chat_id=bot_info['username'],
                file_id=saved_media_data['file_id'],
                caption=updated_caption
            )
            await asyncio.sleep(0.2)  # Rate limiting
        except Exception as e:
            LOGGER(__name__).error(f"Error sending to bot {bot_info['username']}: {e}")
            continue
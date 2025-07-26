

import re
from pyrogram import Client, filters
from pyrogram.types import Message
from config import MULTIPLE_BOT_ALLOWED_DM
from Stranger.utils.helper import get_media_data
from Stranger.utils.database.mongodatabase import add_bot_data



@Client.on_message(filters.private & filters.incoming & MULTIPLE_BOT_ALLOWED_DM)
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
    content_index_match = re.search(r'content_index=([^\s\n]+)', caption)
    
    if not content_match or not content_match or not content_index_match:
        return
    
    content_id = content_match.group(1)
    episode = int(episode_match.group(1)) if episode_match else 1
    content_index = int(content_index_match.group(1))

    # Remove content_id line
    caption = re.sub(r'^content_id=[^\s\n]+\s*\n?', '', caption, flags=re.MULTILINE)
    
    # Remove content_index line
    caption = re.sub(r'^content_index=[^\s\n]+\s*\n?', '', caption, flags=re.MULTILINE)
    
    # Clean up extra whitespace and newlines
    caption = re.sub(r'\n\s*\n', '\n', caption)  # Replace multiple newlines with single
    caption = caption.strip()  # Remove leading/trailing whitespace

    await add_bot_data(
        content_id=content_id,
        content_index=content_index,
        bot_id=client.me.id,
        file_id=media_data['file_id'],
        media_type=media_data['type'],
        caption=caption,
        msg_id=message.id,
        chat_id=message.from_user.id
    )

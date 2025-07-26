"""
Backup status checker for file management system
"""

from pyrogram import Client, filters
from pyrogram.types import Message
from Stranger.utils.file_manager import file_manager
from Stranger.misc import SUDOERS

@Client.on_message(filters.command("backup_status") & filters.private & SUDOERS)
async def check_backup_status(client: Client, message: Message):
    """Check backup processing status for a content_id"""
    try:
        if len(message.text.split()) < 2:
            return await message.reply("Usage: /backup_status <content_id>")
        
        content_id = message.text.split()[1]
        status = file_manager.get_backup_status(content_id)
        
        if status["is_processing"]:
            status_text = f"🔄 **Backup Processing Status**\n\n"
            status_text += f"Content ID: `{content_id}`\n"
            status_text += f"Status: **Processing...**\n"
            status_text += f"Files to process: {status['total_files']}\n"
            status_text += f"⏳ Please wait a few more minutes."
        elif status["total_files"] > 0:
            status_text = f"✅ **Backup Ready**\n\n"
            status_text += f"Content ID: `{content_id}`\n"
            status_text += f"Status: **Ready**\n"
            status_text += f"Files available: {status['total_files']}\n"
            status_text += f"🎉 You can now access this content!"
        else:
            status_text = f"❌ **No Backup Available**\n\n"
            status_text += f"Content ID: `{content_id}`\n"
            status_text += f"Status: **Not Available**\n"
            status_text += f"No backup files found for this content."
        
        await message.reply(status_text)
        
    except Exception as e:
        await message.reply(f"Error checking backup status: {str(e)}")

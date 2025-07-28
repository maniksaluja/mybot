from pyrogram import Client, filters
from pyrogram.types import Message

from Stranger import app, LOGGER
from Stranger.misc import SUDOERS

@app.on_message(filters.command("help") & filters.private & SUDOERS)
async def help_menu(client:Client, message:Message):

    HELP_TEXT = "**🤖 Bot Command Reference**\n\n"
    HELP_TEXT += "**🛡️ Administrative Commands**\n"
    HELP_TEXT += "━━━━━━━━━━━━━━━━━━━━━\n"
    HELP_TEXT += "• `/free [user_id]` - Grant privileges to a user\n"
    HELP_TEXT += "• `/help` - Display this help menu\n"
    HELP_TEXT += "• `/info` - View bot information\n"
    HELP_TEXT += "• `/broadcast` - Send message to all users\n"
    HELP_TEXT += "• `/msg [user_id]` - Send direct message to user\n"
    HELP_TEXT += "• `/settings` - Configure bot settings\n"
    HELP_TEXT += "• `/user` - View bot statistics\n"
    HELP_TEXT += "• `/bot [bot_token]` - Add new file sharing bot\n"
    HELP_TEXT += "• `/pending [group/channel_id] [limit?]` - Accept pending requests\n"
    HELP_TEXT += "• `/sudolist` - View sudo users list\n"
    HELP_TEXT += "• `/addsudo [user_id/username]` - Add sudo user\n"
    HELP_TEXT += "• `/delsudo [user_id/username]` - Remove sudo user\n"
    HELP_TEXT += "• `/reset` - Reset bot stats and database\n"
    HELP_TEXT += "• `/list` - View active subscriptions\n\n"
    HELP_TEXT += "• `/order [order_id]` - Get the details of order using order_id \n\n"

    HELP_TEXT += "**📁 File Management**\n"
    HELP_TEXT += "━━━━━━━━━━━━━━━━━━━━━\n"
    HELP_TEXT += "• `/batch` - Generate multi-file link\n"
    HELP_TEXT += "• `/makeit` - Process batch forwards\n"
    HELP_TEXT += "• `/cancel` - Cancel ongoing process\n"
    HELP_TEXT += "• `/gen` - Generate database links\n"
    HELP_TEXT += "• `/posting` - Create new posts\n"
    HELP_TEXT += "• `/done` - Add to posting category\n\n"

    HELP_TEXT += "**👥 User Commands**\n"
    HELP_TEXT += "━━━━━━━━━━━━━━━━━━━━━\n"
    HELP_TEXT += "• `/start` - Start the bot\n"
    HELP_TEXT += "• `/find [query]` - Search episodes/content\n\n"

    HELP_TEXT += "ℹ️ _For detailed usage, type the command and check its syntax_"

    await message.reply_text(
        HELP_TEXT,
        quote=True,
        disable_notification=True,
        disable_web_page_preview=True
    )
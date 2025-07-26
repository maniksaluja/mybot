import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from Stranger import app
from Stranger.utils.inline import bot_management_panel, bot_setting_panel
from Stranger.utils.database import  get_managed_bots, is_bot_exists
from Stranger.misc import SUDOERS

@app.on_message(filters.command("bot") & filters.private & SUDOERS)
async def addbot(client: Client, message: Message):
    if len(message.command) != 2:
        return await message.reply_text("Usage: /bot [bot token]" , disable_notification=True)
    temp_msg = await message.reply("⏳" , disable_notification=True)

    token = message.text.split()[1]
    
    if await is_bot_exists(token):
        return await temp_msg.edit(text="**This Bot Token Is Already Exist In DataBase**")

    try: 
        success, msg = await app.add_bot(token)
        await temp_msg.edit(msg)
    except Exception as e:
        await temp_msg.edit(f"Error adding bot: {str(e)}")

@app.on_callback_query(filters.regex("bot_management"))
async def bm_setting(client: Client, callback_query: CallbackQuery):
    # Get all bots from database
    all_bots = await get_managed_bots()
    if not all_bots:
        btn = [
            [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data=f"settings_back_helper"),
            InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾",callback_data="close")]
        ]
        return await callback_query.edit_message_text(
            "**No Bots Are Added Yet. Use /bot [token] Command To Add Bots.",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    
    btn = bot_management_panel(all_bots)
    return await callback_query.edit_message_text(
        "**Bot Management Settings **",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@app.on_callback_query(filters.regex("bot_setting") & SUDOERS)
async def bot_setting(client: Client, callback_query: CallbackQuery):
    data = callback_query.data.strip()
    bot_username = str(data.split("|")[-1].strip())
    
    # Get bot info from database instead of managed_bots
    all_bots = await get_managed_bots()
    bot_info = next((bot for bot in all_bots if bot["username"] == bot_username), None)
    
    if not bot_info:
        return await callback_query.answer("Bot Not Found", show_alert=True)
    
    btn = bot_setting_panel(bot_info)
    return await callback_query.edit_message_text(
        f"Bot Setting @{bot_info['username']}", 
        reply_markup=InlineKeyboardMarkup(btn)
    )

@app.on_callback_query(filters.regex("bot_status") & SUDOERS)
async def bot_status(client: Client, callback_query: CallbackQuery):
    data = callback_query.data.strip()
    bot_username = str(data.split("|")[1].strip())
    query = str(data.split("|")[-1].strip())
    user_id = callback_query.from_user.id
    
    # Find bot in database
    all_bots = await get_managed_bots()
    bot_info = next((bot for bot in all_bots if bot["username"] == bot_username), None)
    
    if not bot_info:
        return await callback_query.answer("Bot Not Found", show_alert=True)
    
    if query == "delete":
        btn = [
            [
                InlineKeyboardButton("𝖸𝖾𝗌", callback_data=f"bot_delete|{bot_username}|yes"),
                InlineKeyboardButton("𝖭𝗈", callback_data=f"bot_delete|{bot_username}|no")
            ]
        ]
        return await callback_query.edit_message_text(
            "**Are You Sure You Want To Delete This BOT??**",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    
    success, msg = await app.set_bot_status(bot_info["bot_token"], query)
    await callback_query.message.delete()
    if not success:
        return await app.send_message(chat_id=user_id, text=msg, disable_notification=True)
    
    
    temp = await app.send_message(
        chat_id=user_id,
        text=f"Bot Has Been Activated {'Enabled' if query == 'active' else 'Disabled'}", disable_notification=True
    )
    
    # Refresh bot management panel
    all_bots = await get_managed_bots()  # Get fresh data
    btn = bot_management_panel(all_bots)
    await app.send_message(
        chat_id=user_id,
        text=f"Bot Setting @{bot_info['username']}",
        reply_markup=InlineKeyboardMarkup(btn)
    )
    await asyncio.sleep(2)
    return await temp.delete()

@app.on_callback_query(filters.regex('bot_delete') & SUDOERS)
async def bot_delete(client: Client, callback_query: CallbackQuery):
    data = callback_query.data.strip()
    bot_username = str(data.split("|")[1].strip())
    query = str(data.split("|")[-1].strip())
    
    # Get bot info from database instead of managed_bots
    all_bots = await get_managed_bots()
    bot_info = next((bot for bot in all_bots if bot["username"] == bot_username), None)
    
    if not bot_info:
        return await callback_query.answer("Bot Not Found", show_alert=True)
        
    if query == 'yes':
        await app.remove_bot(bot_info['bot_token'])
        try:
            await callback_query.answer("Token Successfully Deleted From DataBase.", show_alert=True)
        except:
            pass

    # Refresh bot management panel
    all_bots = await get_managed_bots()
    if not all_bots:
        btn = [
            [InlineKeyboardButton(text="𝖡𝖺𝖼𝗄", callback_data="settings_back_helper"),
            InlineKeyboardButton(text="𝖢𝗅𝗈𝗌𝖾", callback_data="close")]
        ]
        return await callback_query.edit_message_text(
            "No Bots Found.\nYou Can Add Bots Using /bot [token] Command.",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    
    btn = bot_management_panel(all_bots)
    return await callback_query.edit_message_text(
        text="**Bot Management Settings**",
        reply_markup=InlineKeyboardMarkup(btn)
    )

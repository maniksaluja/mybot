from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from Stranger import app, LOGGER
from Stranger.utils.database import episode_counter
from Stranger.core.mongo import mongodb
from Stranger.misc import SUDOERS


@app.on_message(filters.command("reset") & SUDOERS)
async def reset(client: Client, message: Message):
    """Reset the bot's data."""
    btn=[
        [
            InlineKeyboardButton(text="𝖱𝖾𝗌𝖾𝗍 𝖤𝗉𝗂𝗌𝗈𝖽𝖾", callback_data="reset_database | episode"),
        ],
        [
            InlineKeyboardButton(text="𝖱𝖾𝗌𝖾𝗍 𝖲𝗎𝖻𝗌𝖼𝗋𝗂𝗉𝗍𝗂𝗈𝗇 ", callback_data="reset_database | subscription"),
        ],
        [
            InlineKeyboardButton(text="𝖥𝖺𝖼𝗍𝗈𝗋𝗒 𝖱𝖾𝗌𝖾𝗍", callback_data="reset_database | all"),
        ]
    ]
    return await message.reply_text("**Choose Your Database Type For CleanUp.**", reply_markup=InlineKeyboardMarkup(btn),disable_notification=True)

@app.on_callback_query(filters.regex("reset_database") & SUDOERS)
async def reset_database(client: Client, callback_query: CallbackQuery):
    """Reset the bot's data based on the user's choice."""
    data = callback_query.data.split("|")
    query = data[1].strip()
    chat_id = callback_query.message.chat.id

    if query == "episode":
        await callback_query.message.edit("**Resetting Episode Data...**")
        await episode_counter.reset_count()
        await callback_query.message.edit("**Episode Data Reset successfully.**")

    elif query == "subscription":
        await callback_query.message.edit("**Removing All Subscriptions...**")
        try:
            collections = await mongodb.list_collection_names()
            total_docs = 0
            
            if 'subscription' in collections:
                sub_count = await mongodb.subscription.count_documents({})
                total_docs += sub_count
                
            if 'users' in collections:
                users_count = await mongodb.users.count_documents({})
                total_docs += users_count

            await callback_query.message.edit(f"**>We Found {total_docs} Documents To Rremove...**")
            
            if 'subscription' in collections:
                await mongodb.subscription.drop()
        
            if 'users' in collections:
                await mongodb.users.drop()
            
            await callback_query.message.edit(f"**Successfully Removed {total_docs} Documents From Subscription.**")
        except Exception as e:
            LOGGER(__name__).error(f"Error: {str(e)}")
            await callback_query.message.edit(f"Error in removing subscriptions. Error : {e}")
    
    elif query == "all":
        await callback_query.message.edit("**Removing All Data...**")
        try:
            collections = await mongodb.list_collection_names()
            total_docs = 0
            
            # Count documents in all collections
            for collection in collections:
                count = await mongodb[collection].count_documents({})
                total_docs += count
            
            await callback_query.message.edit(f">**We Found {total_docs} Documents In {len(collections)} Collections...**")
            
            # Drop all collections
            for collection in collections:
                if collection != "managed_bots":
                    await mongodb[collection].drop()
            
            await callback_query.message.edit(f"**Successfully Removed {total_docs} Documents From {len(collections)} Collections.**")
            await callback_query.message.edit("**All Data Reset Successfully.**")
            
        except Exception as e:
            LOGGER(__name__).error(f"Error: {str(e)}")
            await callback_query.message.edit(f"Error in removing all data. Error: {e}")
    

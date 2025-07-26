from pyrogram import Client, filters
from pyrogram.types import Message,  CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import ListenerTimeout

from Stranger import LOGGER
from config import FEEDBACK_CHANNEL, USELESS_CHANNEL

@Client.on_callback_query(filters.regex("admin_upload"))
async def admin_upload(client:Client, callback_query: CallbackQuery):
    """This function handles the admin upload button click."""
    try:
        msg = callback_query.message.reply_to_message

        if msg.media_group_id:
            snt = await client.copy_media_group(
                chat_id=FEEDBACK_CHANNEL,
                from_chat_id=USELESS_CHANNEL,
                message_id=msg.id
            )
            await snt[0].reply_text(
                text="**Requesting Content. If Anyone Can \n Provide It, Please Share.With US**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="𝘚𝘩𝘢𝘳𝘦 𝘞𝘪𝘵𝘩 𝘜𝘚", url = "https://t.me/Cute_GirlTG")],
                    ])
            )
        else:
            snt = await msg.copy(chat_id=FEEDBACK_CHANNEL)
            await snt.reply_text(
                text="**Requesting Content. If Anyone Can \n Provide It, Please Share.With US**",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="𝘚𝘩𝘢𝘳𝘦 𝘞𝘪𝘵𝘩 𝘜𝘚", url = "https://t.me/CuteGirlTG")],
                    ])
            )
        return await callback_query.edit_message_text("**This Request Successfully Uploaded On Share&Care**", reply_markup=None)
    except Exception as e:
        LOGGER(__name__).error(f"Error: {e}")
        return

@Client.on_callback_query(filters.regex("admin_reject"))
async def admin_reject(client:Client, callback_query: CallbackQuery):
    """This function handles the admin reject button click."""
    try:
        user_id = int(callback_query.data.split("|")[-1])
        msg = callback_query.message.reply_to_message

        me = await client.get_me()

        btn = [
                [
                    InlineKeyboardButton(text="𝘠𝘦𝘴", callback_data=f"feedback_reply|yes|{user_id}"),
                    InlineKeyboardButton(text="𝘕𝘰", callback_data=f"feedback_reply|no|{user_id}")
                ]
            ]
        await client.send_message(
                chat_id=callback_query.from_user.id, 
                text=f"**You Want To say Something This User About This..** [Request]({msg.link})",
                disable_web_page_preview=True,
                disable_notification=True,
                reply_markup=InlineKeyboardMarkup(btn)
                )
        
        await callback_query.edit_message_text(f"**REQUEST REJECTED \n> Check Your Inbox I sended You Msg Related This Request Check this Bot Inbox** @{me.username}")

    except Exception as e:
        LOGGER(__name__).error(f"Error: {e}")


@Client.on_callback_query(filters.regex("feedback_reply"))
async def admin_reply(client:Client, callback_query: CallbackQuery):
    query = callback_query.data.split("|")[1]
    user_id = callback_query.data.split("|")[-1]
    chat = callback_query.message.chat

    if query == "yes":
        user = await client.get_users(user_id)
        try:
            await callback_query.message.delete()
            msg_to_send:Message = await chat.ask(
            f"**Okay Now You Can Type Your Msg For** {user.mention}",
            timeout=300
        )   
            temp_msg:Message = msg_to_send.sent_message

            if msg_to_send.command:
                return await temp_msg.edit("**Process Cancelled**")
            await client.send_sticker(chat_id=user_id, sticker="CAACAgUAAxkBAAEN0QNns2qLA-RAO7o7xVc3KiDlwgFrXQAC9xoAAkRgeFV5uAYVT2v9CzYE", disable_notification=True)
            await msg_to_send.copy(
                chat_id=user_id
            )
            await temp_msg.edit(f"**Successfully Replied To** {user.mention}")
        except ListenerTimeout:
            return await client.send_message(chat_id=chat.id, text= f"**Process Cancelled**")
        except Exception as e:
            LOGGER(__name__).error(f"Error in getting message from admin: {e}")
            return await client.send_message(chat_id=chat.id, text=f"Error: {e}")
    elif query == "no":
       await client.send_message(chat_id=chat.id, text="OK , Request Reply Is Not Processed")

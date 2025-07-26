import asyncio
import math
import random
from typing import Union
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, ListenerTimeout
from pyrogram.enums import ListenerTypes

from Stranger import app
from Stranger.utils.database import bot_users
from Stranger.utils.helper import find_bot
from Stranger.utils.state import broadcast_state
from Stranger.misc import SUDOERS
from Stranger import LOGGER
from config import BCAST_CHANNEL

broadcast_state.is_broadcasting = False
IS_BROADCASTING = False
TIMEOUT_SECONDS= 120

def order_broadcast_messages(broadcast_messages:list[Message]) -> Union[Message, list[Message]]:
    ordered_bcast_msgs = []
    messages = broadcast_messages.copy()  # Create a copy to avoid modifying original list
    
    while messages:
        message = messages[0]  # Look at first message
        
        if message.media_group_id:
            # Handle media group
            media_group = []
            group_id = message.media_group_id
            
            i = 0
            while i < len(messages):
                if messages[i].media_group_id == group_id:
                    media_group.append(messages.pop(i))
                else:
                    i += 1
                    
            ordered_bcast_msgs.append(media_group)
        else:
            # Handle single message
            ordered_bcast_msgs.append(messages.pop(0))
            
    return ordered_bcast_msgs

@app.on_message(filters.command("bcast") & SUDOERS)
async def broadcast(client: Client, message: Message):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply(" **Allready Under Prosesing**", disable_notification=True)
    chat = message.chat
    
    helper_bot_me = await app.helper_bot.get_me()
    btn = []
    btn.append(
        [
            InlineKeyboardButton(text=f"@{app.username}", callback_data=f"broadcast_bot|{app.username}"),
            InlineKeyboardButton(text=f"@{helper_bot_me.username}", callback_data=f"broadcast_bot|{helper_bot_me.username}")
        ]
    )

    row = []
    bots = app.managed_bots
    
    if len(bots.keys()) != 0:
        for x in bots.keys():
            row.append(InlineKeyboardButton(text=f"@{bots[x]['username']}", callback_data=f"broadcast_bot|{bots[x]['username']}"))
            if len(row) == 2:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
    
    try:
        msg1:CallbackQuery = await chat.ask(
            text = "**Choose The Bot To Broadcast**",
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_notification=True,
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=TIMEOUT_SECONDS
        )
        bot_to_broad = msg1.data.strip().split("|")[1]
        await msg1.message.delete()
    except ListenerTimeout:
        return await message.reply("**Timeout: No Response Received**", disable_notification=True)
    except Exception as e:
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
    
    users = await bot_users.get_users(bot_to_broad)
    if not users:
        return await message.reply("**This Bot Has Zero User In DataBase**", disable_notification=True)
    
    try:
        btn=[
            [
                InlineKeyboardButton("𝘖𝘳𝘪𝘨𝘯𝘢𝘭 𝘉𝘳𝘰𝘢𝘥𝘤𝘢𝘴𝘵 ", callback_data=f"type_of_broadcast|original")
            ],
            [
                InlineKeyboardButton("𝘍𝘢𝘬𝘦 𝘉𝘳𝘰𝘢𝘥𝘤𝘢𝘴𝘵 ", callback_data=f"type_of_broadcast|fake")
            ],
            [
                InlineKeyboardButton("𝘚𝘱𝘦𝘤𝘪𝘧𝘪𝘤 𝘉𝘳𝘰𝘢𝘥𝘤𝘢𝘴𝘵 ", callback_data=f"type_of_broadcast|custom")
            ]
        ]
        msg2:CallbackQuery = await chat.ask(
            text = "**CHOOSE YOUR BROADCAST TYPE:** ",
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_notification=True,
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=TIMEOUT_SECONDS
            )
        broadcast_type = msg2.data.strip().split("|")[1]
        await msg2.message.delete()
    except ListenerTimeout:
        return await message.reply("Timeout: No Response Received", disable_notification=True)
    except Exception as e:
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
    
    if broadcast_type == "custom":
        try:
            msg3:Message = await chat.ask(
                text = f"**Enter The Number Of Users To Broadcast To \n\n Total Users Of This Bot : {len(users)} **",
                listener_type=ListenerTypes.MESSAGE,
                timeout=TIMEOUT_SECONDS
            )
            num_users = int(msg3.text)
            await msg3.delete()
            if num_users < 1:
                return await message.reply("**Invalid Input , Cancelling Broadcasting...**", disable_notification=True)
        except ListenerTimeout:
            return await message.reply("**Timeout: No Response Received**", disable_notification=True)
        except Exception as e:
            LOGGER(__name__).error(f"Error getting message: {e}")
            return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
        
    try:
        broadcast_state.is_broadcasting = True
        btn = [
            [
                InlineKeyboardButton("𝖡𝗋𝗈𝖺𝖽𝖼𝖺𝗌𝗍 ", callback_data=f"broadcast_got_messages")
            ]
        ]
        ask_message:CallbackQuery = await chat.ask(
            text="**Okay Now You Can Share Your Message For Broadcast \n> You Have 2Mins To Share Othervives Time-Out**",
            reply_markup=InlineKeyboardMarkup(btn),
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=TIMEOUT_SECONDS
        )
        await ask_message.message.delete()
        broadcast_messages:list[Message] = broadcast_state.get_messages()
        broadcast_state.is_broadcasting = False
    except ListenerTimeout:
        broadcast_state.is_broadcasting = False
        return await message.reply("**Timeout: No Response Received**",  disable_notification=True)
    except Exception as e:
        broadcast_state.is_broadcasting = False
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
        
    
    try:
        btn = [
            [
                InlineKeyboardButton(text="𝖲𝗍𝗈𝗉 ", callback_data="cancel_the_broadcast")
            ]
        ]
        cancel:CallbackQuery = await chat.ask(
            text="**Preparing For Broadcast, You have 10Sec To Stop Prosesss**",
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_notification=True,
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=10
        )
        if cancel:
            await cancel.message.delete()
            return await cancel.answer("Broadcast Cancelled")
    except ListenerTimeout:
        temp_msg = await app.send_message(chat_id=chat.id,text="**Broadcast Started**")
    except Exception as e:
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)

    ordered_bcast_msgs = order_broadcast_messages(broadcast_messages)
    if len(ordered_bcast_msgs) == 0:
        return await temp_msg.edit(**"There Is No Message For Broadcast**")
    if len(ordered_bcast_msgs) > 1:
        return await temp_msg.edit("**Please Give Only One Message To Broadcast**")
    
    bcast_msgs = ordered_bcast_msgs[0]
    bcast_msg = bcast_msgs[0] if isinstance(bcast_msgs, list) else bcast_msgs

    is_forwarded = True if bcast_msg.forward_from_chat or bcast_msg.forward_from else False
    is_media_group = True if bcast_msg.media_group_id else False
    chat_id = message.chat.id

    IS_BROADCASTING = True

    if broadcast_type == "fake":
        total = max(len(users), 1)  # Ensure minimum 1 user
        successful = 0
        blocked = 0
        deleted = 0
        unsuccessful = 0
        
        await asyncio.sleep(total/2)
        
        # Calculate percentages with smaller ranges for few users
        if total < 5:
            max_percent = 20  # Max 20% for each category when few users
        else:
            max_percent = 8   # Original 8% for larger user counts
            
        # Calculate counts with max() to ensure non-negative
        blocked = max(0, math.floor(total * (random.randint(0, max_percent))/100))
        deleted = max(0, math.floor(total * (random.randint(0, max_percent))/100))
        unsuccessful = max(0, math.floor(total * (random.randint(0, max_percent))/100))
        
        # Calculate successful ensuring it's not negative
        successful = max(0, total - (blocked + deleted + unsuccessful))
        
        status = f"""<b><u>Broadcast Completed</u
        
Total Users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked Users: <code>{blocked}</code>
Deleted Accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""
        
        IS_BROADCASTING = False
        return await temp_msg.edit(status)
    else:
        users_to_broadcast = random.sample(users, min(num_users, len(users))) if broadcast_type == "custom" else users
        total = len(users_to_broadcast)
        successful = 0
        blocked = 0
        deleted = 0
        unsuccessful = 0

        if bot_to_broad == app.username:
            bot_client:Client = app
        elif bot_to_broad == helper_bot_me.username:
            bot_client:Client = app.helper_bot
        else:
            bot = find_bot(app.managed_bots, bot_to_broad)
            if not bot:
                return await temp_msg.edit("Something Went Wrong")
            bot_client:Client = bot['bot']
        
        if is_forwarded:
            if is_media_group:
                grp_msgs_ids = [x.id for x in bcast_msgs]
                log_msg = await app.forward_messages(chat_id=BCAST_CHANNEL, from_chat_id=chat.id, message_ids=grp_msgs_ids)
                log_grp_msgs_ids = [x.id for x in log_msg]
            else:
                log_msg = await bcast_msg.forward(BCAST_CHANNEL)  
        else:
            if is_media_group:
                log_msg = await app.copy_media_group(chat_id=BCAST_CHANNEL, from_chat_id=chat.id, message_id=bcast_msg.id)
                log_msgs = log_msg[0]
            else:
                log_msg = await bcast_msg.copy(BCAST_CHANNEL)
        
        error_counts = {}

        for count, i in enumerate(users_to_broadcast, 1):
            if i in SUDOERS:
                continue
            try:
                if is_forwarded:
                    if is_media_group:
                        await bot_client.forward_messages(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_ids=log_grp_msgs_ids, 
                            disable_notification=False
                            )
                    else:
                        await bot_client.forward_messages(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_ids=log_msg.id,
                            disable_notification=False
                            )
                else:
                    if is_media_group:
                        await bot_client.copy_media_group(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_id=log_msgs.id,
                            disable_notification=False
                            )
                    else:
                        await bot_client.copy_message(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_id=log_msg.id,
                            disable_notification=False
                            )
                successful += 1
            except FloodWait as e:
                await asyncio.sleep(int(e.x))
                if is_forwarded:
                    if is_media_group:
                        await bot_client.forward_messages(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_ids=log_grp_msgs_ids, 
                            disable_notification=False
                            )
                    else:
                        await bot_client.forward_messages(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_ids=log_msg.id,
                            disable_notification=False
                            )
                else:
                    if is_media_group:
                        await bot_client.copy_media_group(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_id=log_msgs.id,
                            disable_notification=False
                            )
                    else:
                        await bot_client.copy_message(
                            chat_id=i, 
                            from_chat_id=BCAST_CHANNEL, 
                            message_id=log_msg.id,
                            disable_notification=False
                            )
                successful += 1
            except UserIsBlocked:
                await bot_users.del_user(bot_to_broad, i)
                blocked += 1
            except InputUserDeactivated:
                await bot_users.del_user(bot_to_broad, i)
                deleted += 1
            except Exception as e:
                # LOGGER(__name__).info(f"Error in broadcasting : {e}")
                unsuccessful += 1

                error_str = str(e)
                error_type = "Unknown"
                
                if "Telegram says:" in error_str:
                    try:
                        error_parts = error_str.split("]")[0].split("[")[1].strip()
                        error_code = error_parts.split(" ", 1)[1] if " " in error_parts else error_parts
                        error_type = error_code
                    except:
                        pass
                
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

            if count % 15 == 0:
                seconds_left = int((total - count) * 0.7)
                
                if seconds_left < 60:
                    time_left = f"{seconds_left} seconds"
                elif seconds_left < 3600:
                    minutes = seconds_left // 60
                    seconds = seconds_left % 60
                    time_left = f"{minutes} minutes {seconds} seconds"
                else:
                    hours = seconds_left // 3600
                    minutes = (seconds_left % 3600) // 60
                    seconds = seconds_left % 60
                    time_left = f"{hours} hours {minutes} minutes {seconds} seconds"
                
                progress = f"<b>Broadcasting in Progress</b>\n\n<b>Completed:</b> {count}/{total} (<code>{count/total*100:.1f}%</code>)\n<b>Success:</b> {successful} (<code>{successful/total*100:.1f}%</code>)\n<b>Blocked:</b> {blocked} (<code>{blocked/total*100:.1f}%</code>)\n<b>Deleted:</b> {deleted} (<code>{deleted/total*100:.1f}%</code>)\n<b>Failed:</b> {unsuccessful} (<code>{unsuccessful/total*100:.1f}%</code>)\n\n<b>Time left:</b> {time_left}"
                await temp_msg.edit(progress)
            await asyncio.sleep(0.5)
        
        status = f"""<b><u>Broadcast Completed</u>

Total Users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked Users: <code>{blocked}</code>
Deleted Accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""

        if error_counts:
            status += "\n\n<b>Error Breakdown:</b>"
            for error_type, count in error_counts.items():
                status += f"\n<code>{error_type}</code>: {count}"
        
        IS_BROADCASTING = False
        await app.delete_messages(
            chat_id=BCAST_CHANNEL,
            message_ids=[x.id for x in log_msg] if isinstance(log_msg, list) else log_msg.id
        )
        return await temp_msg.edit(status)

@app.on_message(filters.command("msg") & SUDOERS)
async def send_nsg(client:Client, message:Message):
    if len(message.command) != 2:
        return await message.reply("Usage /msg [user_id]" , disable_notification=True)
    
    user = int(message.text.split(None, 1)[1])
    if user <= 0:
        return await message.reply("**Invalid User ID**", disable_notification=True)

    chat = message.chat
    
    helper_bot_me = await app.helper_bot.get_me()
    btn = []
    btn.append(
        [
            InlineKeyboardButton(text=f"@{app.username}", callback_data=f"broadcast_bot|{app.username}"),
            InlineKeyboardButton(text=f"@{helper_bot_me.username}", callback_data=f"broadcast_bot|{helper_bot_me.username}")
        ]
    )

    bots = app.managed_bots
    row = []
    if len(bots.keys()) != 0:
        for token in bots.keys():
            row.append(InlineKeyboardButton(text=f"@{bots[token]['username']}", callback_data=f"broadcast_bot|{bots[token]['username']}"))
            if len(row) == 2:
                btn.append(row)
                row = []
        if row:
            btn.append(row)
    try:
        msg1:CallbackQuery = await chat.ask(
            text = "**Choose The Bot**",
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_notification=True,
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=TIMEOUT_SECONDS
        )
        bot_to_send = msg1.data.strip().split("|")[1]
        await msg1.message.delete()
    except ListenerTimeout:
        return await message.reply("**Timeout: No Response Received**", disable_notification=True)
    except Exception as e:
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
    
    try:
        broadcast_state.is_broadcasting = True
        btn = [
            [
                InlineKeyboardButton("𝖣𝗂𝗋𝖾𝖼𝗍 𝖬𝖲𝖦 ", callback_data=f"message_to_send_to_user")
            ]
        ]
        ask_message:CallbackQuery = await chat.ask(
            text="Okay Now You Can Share Your Message For Direct MSG \n> You Have 2Mins To Share Othervives Time-Out",
            reply_markup=InlineKeyboardMarkup(btn),
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=TIMEOUT_SECONDS
        )
        await ask_message.message.delete()
        broadcast_messages:list[Message] = broadcast_state.get_messages()
        broadcast_state.is_broadcasting = False
    except ListenerTimeout:
        broadcast_state.is_broadcasting = False
        return await message.reply("**Timeout: No Response Received**", disable_notification=True)
    except Exception as e:
        broadcast_state.is_broadcasting = False
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}", disable_notification=True)
    
    try:
        btn = [
            [
                InlineKeyboardButton(text="𝖲𝗍𝗈𝗉", callback_data="cancel_the_message")
            ]
        ]
        cancel:CallbackQuery = await chat.ask(
            text="**Preparing For Broadcast, You have 10Sec To Stop Prosesss**",
            reply_markup=InlineKeyboardMarkup(btn), 
            disable_notification=True,
            listener_type=ListenerTypes.CALLBACK_QUERY,
            timeout=5
        )
        if cancel:
            return await message.reply("**Message cancelled**", disable_notification=True)
    except ListenerTimeout:
        temp_msg = await app.send_message(chat_id=chat.id,text="**Wait Sending Message**")
    except Exception as e:
        LOGGER(__name__).error(f"Error getting message: {e}")
        return await message.reply(f"Error occurred: {str(e)}" , disable_notification=True)

    ordered_bcast_msgs = order_broadcast_messages(broadcast_messages)
    if len(ordered_bcast_msgs) == 0:
        return await temp_msg.edit("**There Is No Massage To share This User**")
    if len(ordered_bcast_msgs) > 1:
        return await temp_msg.edit("**Please Give Only One Message To Send**")
    
    bcast_msgs = ordered_bcast_msgs[0]
    bcast_msg = bcast_msgs[0] if isinstance(bcast_msgs, list) else bcast_msgs
    
    try:
        if bot_to_send == app.username:
            bot_client:Client = app
        elif bot_to_send == helper_bot_me.username:
            bot_client:Client = app.helper_bot
        else:
            bot = find_bot(app.managed_bots, bot_to_send)
            if not bot:
                return await temp_msg.edit("Something Went wrong")
            bot_client:Client = bot['bot']
        
        await bot_client.send_sticker(
            chat_id=user,
            sticker="CAACAgUAAxkBAAEN0QNns2qLA-RAO7o7xVc3KiDlwgFrXQAC9xoAAkRgeFV5uAYVT2v9CzYE",
            disable_notification=False
            )
        
        if bcast_msg.forward_from or bcast_msg.forward_from_chat:
            if bcast_msg.media_group_id:
                grp_msgs_ids = [x.id for x in bcast_msgs]
                log_msg = await app.forward_messages(
                    chat_id=BCAST_CHANNEL, 
                    from_chat_id=chat.id, 
                    message_ids=grp_msgs_ids
                    )
                await bot_client.forward_messages(
                    chat_id=user, 
                    from_chat_id=BCAST_CHANNEL, 
                    message_ids=[x.id for x in log_msg],
                    disable_notification=False
                    )
            else:
                log_msg = await bcast_msg.forward(BCAST_CHANNEL)
                await bot_client.forward_messages(
                    user, 
                    BCAST_CHANNEL, 
                    log_msg.id, 
                    disable_notification=False
                    )
        else:
            if bcast_msg.media_group_id:
                log_msg = await app.copy_media_group(
                    chat_id=BCAST_CHANNEL, 
                    from_chat_id=chat.id, 
                    message_id=bcast_msg.id
                    )
                await bot_client.copy_media_group(
                    chat_id=user,
                    from_chat_id=BCAST_CHANNEL,
                    message_id=log_msg[0].id,
                    disable_notification=False
                )
            else:
                log_msg = await bcast_msg.copy(BCAST_CHANNEL)
                await bot_client.copy_message(user, BCAST_CHANNEL, log_msg.id, disable_notification=False)
        
        await app.delete_messages(
            chat_id=BCAST_CHANNEL,
            message_ids=[x.id for x in log_msg] if isinstance(log_msg, list) else log_msg.id
        )
        return await temp_msg.edit("**Message Send Successfully**")
    except Exception as e:
        LOGGER(__name__).info(e)
        return await temp_msg.edit(f"**Bot Is Unable To Send Message To This User Because, User Blocked The Bot : {e} **")

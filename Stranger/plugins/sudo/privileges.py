import asyncio
import pytz
import datetime
import time
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup,InlineKeyboardButton
from pyrogram.errors import UserAdminInvalid, ChannelPrivate
from pyrogram.enums import ChatMemberStatus
from Stranger import app
from Stranger.misc import SUDOERS
from Stranger.utils.database.mongodatabase import manage_users, get_user, update_user, user_exists, Plan, Subs_Type, get_user_payment_history
from Stranger.utils.inline.privileges import privileges_panel
from Stranger.utils.helper import get_readable_time
from Stranger import LOGGER
from config import ACCESS_TOKEN_PLAN_1, ACCESS_TOKEN_PLAN_2, DOWNLOAD_PLAN_1, DOWNLOAD_PLAN_2, temp_channels, BANNED_USERS

user_auto_delete_tasks = {}

def cancel_auto_delete_task(user_id):
    """Cancel existing auto-delete task for a user and clean up immediately"""
    if user_id in user_auto_delete_tasks:
        user_auto_delete_tasks[user_id].cancel()
        del user_auto_delete_tasks[user_id]

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
            
    except asyncio.CancelledError:
        pass

def reset_auto_delete_timer(func):
    """Decorator to reset auto-delete timer on user interaction"""
    async def wrapper(client, callback_query):
        user_id = callback_query.from_user.id
        cancel_auto_delete_task(user_id) 
        
        result = await func(client, callback_query)
        
        schedule_auto_delete(user_id, [callback_query.message], delay=300)
        
        return result
    return wrapper

@app.on_callback_query(filters.regex("pv_close") & SUDOERS)
async def close_privileges_panel(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # Cancel the auto-delete task when user manually closes
    cancel_auto_delete_task(user_id)
    
    await callback.message.delete()

@app.on_message(filters.command("free") & SUDOERS)
async def free_user(cient:Client , message:Message):
    user_id = message.from_user.id  
    
    if len(message.command) != 2:
        return await message.reply_text("Usage: /free [user_id]",quote=True, disable_notification=True)
    try:
        target_user_id = int(message.command[1])
    except ValueError:
        return await message.reply_text("Invalid User ID provided",quote=True, disable_notification=True)
    
    if not await user_exists(target_user_id):
        await manage_users(target_user_id, "add")
    
    user = await get_user(target_user_id)
    TEXT = ""
    current_time = time.time()
    updated = False
    if user["is_token_verified"]:
        tym = user['token_expiry_time']
        remaining_time = tym - current_time
        if remaining_time > 0:
            TEXT += f">**AccessToken Expiry in :{get_readable_time(remaining_time)} **\n"
        else:
            user['is_token_verified'] = False
            user['token_expiry_time'] = 0
            user['token_plan'] = Plan.NONE
            user['access_token_type'] = Subs_Type.NONE
            updated = True
    
    if user["is_download_verified"]:
        tym = user["download_expiry_time"]
        remaining_time = tym - current_time
        if remaining_time > 0:
            TEXT += f"\n>**Download Expiry in : {get_readable_time(remaining_time)} **"
        else:
            user['is_download_verified'] = False
            user['download_expiry_time'] = 0
            user['download_plan'] = Plan.NONE
            user['access_download_type'] =Subs_Type.NONE
            updated = True
    
    # Get user's last 2 payment details
    payment_history = await get_user_payment_history(target_user_id, limit=2)
    if payment_history:
        TEXT += f"\n\n**📊 Payment History (Last 2 Orders):**\n"
        for i, order in enumerate(payment_history, 1):
            payment_status = "✅ Paid" if order['is_paid'] else "❌ Not Paid"
            activation_status = "✅ Activated" if order['is_activated'] else "❌ Not Activated"
            
            # Format amount properly
            amount = order['amount']
            if amount > 100:  # Razorpay stores in paisa (amount * 100)
                amount = amount / 100
            
            # Format date
            created_at = order.get('created_at', 0)
            if created_at:
                try:
                    if isinstance(created_at, (int, float)):
                        date_obj = datetime.datetime.fromtimestamp(created_at)
                    else:
                        date_obj = created_at
                    formatted_date = date_obj.strftime('%B•%d•%Y')
                except:
                    formatted_date = "Unknown"
            else:
                formatted_date = "Unknown"
            
            TEXT += f"\n**Order {i}:**\n"
            TEXT += f">**Order ID:** `{order['order_id']}`\n"
            TEXT += f">**Amount:** ₹{amount:.0f}\n"
            TEXT += f">**Plan:** {order['subscription_type'].replace('_', ' ').title()} - {order['plan_type'].upper()}\n"
            TEXT += f">**Date:** {formatted_date}\n"
            TEXT += f">**Payment:** {payment_status}\n"
            TEXT += f">**Status:** {activation_status}\n"
    else:
        TEXT += f"\n\n**📊 Payment History:** No payments found"
    
    if updated:
        await update_user(target_user_id, user)
    btn = privileges_panel(user , target_user_id)
    
    privileges_msg = await message.reply(f"**Configure User Rights**\n {TEXT}", reply_markup=InlineKeyboardMarkup(btn),quote=True, disable_notification=True)
    
    schedule_auto_delete(user_id, [privileges_msg], delay=300)
    
    return privileges_msg

@app.on_callback_query(filters.regex("update_up") & SUDOERS)
@reset_auto_delete_timer
async def update_user_privileges(client:Client, callback_query:CallbackQuery):
    data = callback_query.data.split("|")
    target_user_id = int(data[1])
    query = data[2]
    user = await get_user(target_user_id)
    
    if query == "token" or query == "download":
        if len(list(app.managed_bots.keys())) == 0:
            return await callback_query.answer("No Bots Added, First Add Bot In Bot Multiple Bot Use /bot [token] To Add Bot")
        first_bot = next(iter(app.managed_bots))
        bot_client:Client = app.managed_bots[first_bot]['bot']
        update = data[-1]
        if update == "None":
            try:
                await bot_client.send_sticker(
                    chat_id=target_user_id,
                    sticker="CAACAgUAAxkBAAENyjpnrwABmAAB7r02IolBWqLecOZ9xVA9AAJYFQACdLYIVS3E_ycgZHh5NgQ", 
                    disable_notification=True
                    )
                await bot_client.send_message(
                    chat_id=target_user_id,
                    text="**Your MemeberShip Cancelled By Admin**",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    text="𝘊𝘰𝘯𝘵𝘢𝘤𝘵 𝘛𝘰 𝘈𝘥𝘮𝘪𝘯",
                                    url="https://t.me/CuteGirlTG?text=%2A%2A%20I%20saw%20my%20subscription%20is%20stopped%20by%20admin%20but%20why%3F%20%2A%2A"
                                    )
                            ]
                        ]
                    ),
                    disable_notification=False
                )            
            except Exception as e:
                LOGGER(__name__).info(f"Error in sending message to user in privileges : {e}")
                pass
            expiry_time = 0
            plan = Plan.NONE
        elif update == "plan1":
            expiry = ACCESS_TOKEN_PLAN_1 if query =="token" else DOWNLOAD_PLAN_1
            exp_time = get_readable_time(expiry)
            expiry_time = time.time() + expiry
            plan = Plan.PLAN1
        else:
            expiry = ACCESS_TOKEN_PLAN_2 if query =="token" else DOWNLOAD_PLAN_2
            expiry_time = time.time() + expiry
            exp_time = get_readable_time(expiry)
            plan = Plan.PLAN2

        if update != "None":
            subs_plan = "Access token" if query=="token" else "Download"
            ist = pytz.timezone('Asia/Kolkata')
            current_time = datetime.datetime.now(ist)
            await bot_client.send_sticker(chat_id=target_user_id, sticker="CAACAgUAAxkBAAEN0PFns1LK5ZRY67nIDjckuVIqPiO_MgACzBcAAq3VCVUmpeGzKjK4wjYE", disable_notification=True)
            await bot_client.send_message(
                chat_id=target_user_id,
                    text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: MANUAL\n•SUBSCRIPTION PLAN: {subs_plan.upper()} \n>• Expires in : {exp_time} **",
                    disable_notification=True
                    )
        
        user[f"is_{query}_verified"] = True
        user[f"{query}_expiry_time"] = expiry_time
        user[f"{query}_plan"] = plan
        user[f"access_{query}_type"] = Subs_Type.TYPE3
    elif query == "ban" or query == "unban":
        if target_user_id in SUDOERS and query == "ban":
                return await callback_query.answer("This User Is A Sudo User. Can't Ban Them.", show_alert=True)
        await callback_query.answer("Hold-On, Its Take Some Seconds" , show_alert=True)
        if query == "ban":
            for c in temp_channels:
                try:
                    about_me = await app.get_chat_member(c, "me")
                    if about_me.status != ChatMemberStatus.ADMINISTRATOR:
                        return await callback_query.answer(f"I Am Not Admin In This Channel. Please Promote Me\n\n {about_me.chat.title}", show_alert=True)
                    
                    if not about_me.privileges.can_restrict_members:
                        return await callback_query.answer(f"I Don't Have The Required Permissions To Ban Users In This Channel. \n\n {about_me.chat.title}", show_alert=True)
                except ChannelPrivate:
                    return await callback_query.answer(f"I Am Not A Part Of This channel. \n\n {c}")
                except Exception as e:
                    LOGGER(__name__).info(f"ERROR in ban user {e}")
                    pass
                try:
                    await app.ban_chat_member(c, target_user_id)
                except UserAdminInvalid:
                    pass
                except Exception as e:
                    LOGGER(__name__).error(e)
            
            BANNED_USERS.add(target_user_id)
        else:

            for c in temp_channels:
                try:
                    about_me = await app.get_chat_member(c, "me")
                    if about_me.status != ChatMemberStatus.ADMINISTRATOR:
                        return await callback_query.answer(f"I Am Not Admin In This Channel. Please Promote Me \n\n {about_me.chat.title}", show_alert=True)
                    
                    if not about_me.privileges.can_restrict_members:
                        return await callback_query.answer(f"I Don't Have The Required Permissions To Ban Users In This Channel. \n\n {about_me.chat.title}", show_alert=True)
                except ChannelPrivate:
                    return await callback_query.answer(f"I Am Not A Part Of This Channel. \n\n {c}")
                except Exception as e:
                    LOGGER(__name__).info(f"ERROR in ban user {e}")
                    pass
                try:
                    await app.unban_chat_member(c,target_user_id)
                except Exception as e:
                    LOGGER(__name__).info(f"Error in unbanning user {e}")

                
            BANNED_USERS.remove(target_user_id)
                

        user['is_banned'] = True if query == "ban" else False
        await callback_query.message.reply(f">User Has Been {'banned' if query == 'ban' else 'unbanned'} From All Groups And {'blocked' if query=='ban' else 'unblocked'} From All The Other Bots",disable_notification=True)
    
    await update_user(target_user_id, user)
    btn = privileges_panel(user , target_user_id)

    TEXT = "**Configure User Rights**\n"
    current_time = time.time()
    if user["is_token_verified"] and (user['token_expiry_time'] - current_time) > 0:
        TEXT += f">**Token Expiry in :** {get_readable_time(user['token_expiry_time'] - current_time)}\n"
    if user["is_download_verified"] and (user['download_expiry_time'] - current_time) > 0:
        TEXT += f">**Download Expiry in :**{get_readable_time(user['download_expiry_time'] - current_time)}\n\n"
    
    try:
        if TEXT != callback_query.message.text:
            return await callback_query.edit_message_text(
                text=TEXT, 
                reply_markup=InlineKeyboardMarkup(btn)
                )
        else:
            return await callback_query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        LOGGER(__name__).error("Error in privilleges: " + str(e))
        return

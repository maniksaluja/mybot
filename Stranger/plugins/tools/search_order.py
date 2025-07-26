from pyrogram import Client, filters
from pyrogram.types import Message
from Stranger.core.razorpay import get_payment_details
from Stranger import app, LOGGER
from Stranger.misc import SUDOERS


@app.on_message(filters.command("order") & SUDOERS)
async def order(client:Client, message: Message):
    try:
        if len(message.command) != 2:
            return await message.reply_text("**Please Provide The Order Id. \n> Usage: /order [order_id]**")
        
        if len(list(app.managed_bots.keys())) == 0:
            return await message.reply_text(">**No Bots Added, First Add Bot In Bot Multiple Bot Use /bot [token] To Add Bot**")

        order_id = message.command[1]
        result = await get_payment_details(order_id)
        if not result:
            return await message.reply_text(f"No Order Found With ID: {order_id}")

        # Create a formatted message with order details
        order_status = result.get("status", "Unknown")
        status_emoji = "✅" if order_status == "paid" else "⏳" if order_status == "created" else "❌"

        ac = result.get('activated')
        
        user = result.get('user_id', None )
        reply_text = f">**#{order_id} ORDER ID FOUND IN DATABASE**\n\n"
        reply_text += f"**STATUS ▷** {status_emoji} {order_status}\n"
        reply_text += f"**USER ID ▷**: [user](tg://user?id={user})\n" if user else f"**User:**: Unknown\n"
        reply_text += f"**USER PAYED▷** ₹{result.get('amount', 'N/A')}\n"
        reply_text += f"**PLAN MODE ▷** {result.get('subscription_type', 'N/A')}\n"
        reply_text += f"**PLAN TYPE ▷** {result.get('plan_type', 'N/A')}\n"
        activated_emoji = "✅" if ac else "❌"
        reply_text += f"**ACTIVATED ▷** {activated_emoji}\n\n"
        if not ac and order_status == "paid":
            reply_text += f"** ACTIVATE LINK ▷** {result['callback_url']}"


        return await message.reply_text(reply_text)
    except Exception as e:
        LOGGER(__name__).error(f"Error in checking order details : {str(e)}")
        return await message.reply_text(f"Error occurred while checking order details. Please try again later. \n\n Error:{str(e)}")

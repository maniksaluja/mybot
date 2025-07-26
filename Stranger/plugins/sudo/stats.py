from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery


from Stranger import app
from Stranger.misc import SUDOERS
from Stranger.utils.database import bot_users, get_subscription_stats, reset_all_subscriptions
from Stranger import LOGGER



@app.on_message(filters.command("user") & SUDOERS)
async def bot_users_stats(client:Client, message:Message):
    bots = app.managed_bots
    TEXT = "•This List Shows The Available Bots And \n Their User Counts. \n\n"
    try:
        users = await bot_users.get_users(app.username)
        TEXT += f"@{app.username} : {len(users)}\n"
        bot_username = await app.helper_bot.get_me()
        TEXT += f"@{bot_username.username} : {len(await bot_users.get_users(bot_username.username))} \n"
        if len(list(app.managed_bots.keys())) != 0:
            for bot in bots:
                bot_username = bots[bot]['username']
                users = await bot_users.get_users(bot_username)
                TEXT += f"@{bot_username} : {len(users)} \n"
        return await message.reply(TEXT,disable_notification=True)
    except Exception as e:
        LOGGER(__name__).info(f"Error occurred in getting user stats: {e}")
        return await message.reply(f"Something went wrong. \n Error:{e}",disable_notification=True)
    

def formate_time(x: float) -> str:
    dt = datetime.fromtimestamp(x)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

@app.on_message(filters.command("list") & SUDOERS)
async def subscriptios_stats(client:Client, message:Message):
    temp_msg = await message.reply("**HOLD-ON !!!! \n Collecting Data Form DataBase.. ** ",disable_notification=True)
    try:

        data = await get_subscription_stats()
        stats = data['subscriptions']

        end_date = datetime.now()
        start_date= data['dateRange']['oldest']

        if not start_date:
            start_date = end_date

        date_format = "%d/%m/%Y"
        output = f"**SUBSCRIPTION STATISTICS** \n> **{start_date.strftime(date_format)} TO {end_date.strftime(date_format)}\n\n**"

        # Access Keys section
        access_p1_paid = stats.get("access_plan1_payment", 0)
        access_p1_ads = stats.get("access_plan1_ads", 0)
        access_p2_paid = stats.get("access_plan2_payment", 0)

        output += "<pre> **≼ACCESKEY≽** </pre>\n"
        output += f"**•1DAY User Count: {access_p1_paid}P ≼≽ {access_p1_ads}ADS \n**"
        output += f"**•30DAYS  User Count: {access_p2_paid}P\n**"
        output += f"**TOTAL  ACCESKEY▷ {access_p1_paid + access_p1_ads + access_p2_paid}\n\n**"

        # Downloads section
        download_p1_paid = stats.get("download_plan1_payment", 0)
        download_p2_paid = stats.get("download_plan2_payment", 0)
        total_downloads = download_p1_paid + download_p2_paid
      
        output += f"<pre> **≼DOWNLOAD KEY≽** </pre>\n"
        output += f"**•12H User Count: {download_p1_paid}P \n**"
        output += f"**•30DAYS User Count: {download_p2_paid}P \n**"
        output += f"**TOTAL  DOWNLOADS▷ {total_downloads}\n\n**"

        # Overall total
        total_users = sum(stats.values())
        output += f"<pre> **▽ALL-OVER  KEY GENERATED▽** </pre>\n                      {total_users} **"

        btn = [
            [
                InlineKeyboardButton(text="𝖱𝖾𝗌𝖾𝗍 𝖧𝗂𝗌𝗍𝗈𝗋𝗒 ", callback_data="reset_subs_stats")
            ]
        ]

        await temp_msg.delete()
        await message.reply_text(text=output,reply_markup=InlineKeyboardMarkup(btn),disable_notification=True)
    except Exception as e:
        LOGGER(__name__).info(f"Error occured in getting user subscription stats : {e}")
        return await temp_msg.edit(f"Some error has occurred. \n Error :{e}")
    

@app.on_callback_query(filters.regex("reset_subs_stats") & SUDOERS)
async def reset_subs_stats(client:Client, callback_query:CallbackQuery):
    await reset_all_subscriptions()
    await callback_query.answer("All Subscription History Has Been Reset", show_alert=True)
    return await callback_query.message.delete()


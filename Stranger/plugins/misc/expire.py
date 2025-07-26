import asyncio
from datetime import datetime, timedelta
import pytz

from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserIsBlocked

from Stranger import app
from Stranger.utils.database.mongodatabase import get_all_users_with_details, get_settings
from Stranger.utils.helper import get_readable_time
from config import (
    ACCESS_TOKEN_PLAN_1,
    ACCESS_TOKEN_PLAN_2,
    ACCESS_TOKEN_PLAN_1_PRICE,
    ACCESS_TOKEN_PLAN_2_PRICE,
    DOWNLOAD_PLAN_1, 
    DOWNLOAD_PLAN_1_PRICE, 
    DOWNLOAD_PLAN_2, 
    DOWNLOAD_PLAN_2_PRICE 
)
from strings import QUERY_LINK
from Stranger import LOGGER

SUBSCRIPTION_CHECK_TIME = 3600


async def notify_user(user_id: int, subscription_type: str, settings):
    """Send notification to user about subscription expiry"""
    try:
        first_bot = next(iter(app.managed_bots))
        bot_client:Client = app.managed_bots[first_bot]['bot']
        await bot_client.send_sticker(
                    chat_id=user_id,
                    sticker="CAACAgUAAxkBAAEOFrBn1dIkAmAe-n7abGSr_975OFvpeAAC6RoAAl8-mVbBTsrcb8MGsjYE",
                    disable_notification=True
                    )
        if subscription_type == "token":
            btn = []
            rows = []
            if settings['url_shortner'] or settings['payment_gateway']:
                rows.append(
                        InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_1)}",callback_data=f"access_token_subscribe")
                )
            if settings['payment_gateway']:
                rows.append(
                    InlineKeyboardButton(f"{get_readable_time(ACCESS_TOKEN_PLAN_2)}",callback_data="payment|access_token|plan2")
                )

            if rows:
                btn.append(rows)
            else:
                btn =None
        else:
            if not settings['payment_gateway']:
                btn=None
            else:
                btn = [
                    [InlineKeyboardButton(f"{get_readable_time(DOWNLOAD_PLAN_1)} -- Rs{DOWNLOAD_PLAN_1_PRICE}", callback_data=f"payment|download|plan1"),
                    InlineKeyboardButton(f"{get_readable_time(DOWNLOAD_PLAN_2)} -- Rs{DOWNLOAD_PLAN_2_PRICE}", callback_data=f"payment|download|plan2")],
                    ]

        message = (
            f" **SUBSCRIPTION EXPIRING.....**\n\n>"
            f"**Your {subscription_type} Memebership Will Expire in 59Mins.**\n>"
            "**You Can RENEW Your Memebership To Continue Using Our services. \n\nCHOOSE YOUR PLAN TO RENEW** "
            
        )
        try:
            await bot_client.send_message(
            chat_id=user_id, 
            text=message,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(btn) if btn else None,
            disable_notification=False
            )
        except UserIsBlocked:
            pass
        except Exception as e:
            raise Exception(e)
    except Exception as e:
        LOGGER(__name__).warning(f"Failed to send notification to user {user_id}: {e}")

async def subscription_check():
    """Check for expiring subscriptions every minute"""
    while True:
        try:
            # Get all users with their complete details
            current_time = datetime.now(pytz.UTC)
            one_hour_later = current_time + timedelta(hours=1)

            # Get all users with their settings
            all_users = await get_all_users_with_details()

            settings = await get_settings()

            for user in all_users:
                user_id = user['user_id']
                user_settings = user['settings']

                # Check token subscription
                if user_settings.get('is_token_verified'):
                    token_expiry = datetime.fromtimestamp(
                        user_settings.get('token_expiry_time', 0),
                        pytz.UTC
                    )
                    # If expiry is within the next hour
                    if current_time < token_expiry <= one_hour_later:
                        await notify_user(user_id, "token", settings)

                # Check download subscription
                if user_settings.get('is_download_verified'):
                    download_expiry = datetime.fromtimestamp(
                        user_settings.get('download_expiry_time', 0),
                        pytz.UTC
                    )
                    # If expiry is within the next hour
                    if current_time < download_expiry <= one_hour_later:
                        await notify_user(user_id, "download", settings)

        except Exception as e:
            LOGGER(__name__).warning(f"Error in subscription check: {e}")

        # Check every hour
        await asyncio.sleep(SUBSCRIPTION_CHECK_TIME)

# Start the subscription checker task
asyncio.create_task(subscription_check())

import asyncio
import threading
from pyrogram import idle
from Stranger import  app ,userbot
from config import BANNED_USERS
from .logger import LOGGER
from Stranger.utils.database import get_banned_users
from Stranger.plugins.tools.reaction_post import restore_daily_reaction_posts, deactivate_old_posts
from Stranger.utils.file_manager_init import startup_file_manager
from Stranger.core.webhook import run_webhook_server_sync, process_webhook_events_queue

webhook_thread = None
loop = asyncio.get_event_loop()
async def init():
    global webhook_thread

    try:
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    
    # Start userbot and main bot
    await userbot.start()
    await app.start()

    # Initialize file manager after userbot starts
    await startup_file_manager()

    # Restore daily reaction posts and cleanup old ones
    await restore_daily_reaction_posts()
    await deactivate_old_posts(days_to_keep=7)

    # Start webhook server in a separate thread
    try:
        webhook_thread = threading.Thread(
            target=run_webhook_server_sync,
            args=('0.0.0.0', 80),
            daemon=True
        )
        webhook_thread.start()
        LOGGER("Stranger").info("FastAPI webhook server started alongside bot")
    except Exception as e:
        LOGGER("Stranger").error(f"Failed to start webhook server: {e}")
        LOGGER("Stranger").info("Bot will continue without webhook server")

    # Start webhook events queue processor
    try:
        asyncio.create_task(process_webhook_events_queue())
        LOGGER("Stranger").info("Webhook events queue processor started")
    except Exception as e:
        LOGGER("Stranger").error(f"Failed to start webhook events queue processor: {e}")

    await idle()
    
    # Graceful shutdown
    LOGGER("Stranger").info("Shutting down bots...")
    try:
        await app.stop()
        await userbot.stop()
        LOGGER("Stranger").info("Bots stopped successfully")
    except Exception as e:
        LOGGER("Stranger").error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    try:
        loop.run_until_complete(init())
    except KeyboardInterrupt:
        pass
    finally:
        LOGGER("Stranger").info("Stopping Stranger Bot! GoodBye")

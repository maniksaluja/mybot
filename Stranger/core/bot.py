from pyrogram import Client
import sys
from datetime import datetime
import os
import asyncio

from config import (
    API_HASH,
    API_ID,
    API_HASH2,
    API_ID2,
    BOT_TOKEN,
    BOT_TOKEN2,
    RFSUB,
    FSUB,
    PENDING_REQUEST,
    RFSUB_CHAT_LINKS,
    FSUB_CHAT_LINKS,
    PENDING_REQUEST_LINKS,
    BOT_ALL_CHANNELS
)
from ..logger import LOGGER
from Stranger.utils.database.mongodatabase import get_managed_bots,add_managed_bot, remove_managed_bot, update_managed_bot



class StrangerBot(Client):
    def __init__(self):
        super().__init__(
            name="Stranger",
            api_hash=API_HASH,
            api_id=API_ID,
            plugins=dict(root="Stranger.plugins"),
            bot_token=BOT_TOKEN,
            workers=80
        )
        self.LOGGER = LOGGER
        self.managed_bots = {}

    async def start(self):
        await super().start()
        usr_bot_me = await self.get_me()
        self.username = usr_bot_me.username
        self.id = usr_bot_me.id
        self.uptime = datetime.now()

        helper_bot = Client(
            name="Stranger_helper",
            api_hash=API_HASH,
            api_id=API_ID,
            bot_token=BOT_TOKEN2,
            plugins=dict(root="Stranger.plugins2"),
            workers=30
        )
        await helper_bot.start()
        self.helper_bot = helper_bot
        helper_bot_me = await helper_bot.get_me()
        self.helper_bot_username = helper_bot_me.username

        err = False
        for c in RFSUB:
            try:
                await self.get_chat(c)
                await self.helper_bot.get_chat(c)
                link = await self.create_chat_invite_link(c, creates_join_request=True)
                RFSUB_CHAT_LINKS[c] = link.invite_link
            except Exception as e:
                self.LOGGER(__name__).warning(e)
                self.LOGGER(__name__).warning(f"Please Double check the Channel id value and Make sure Bot is Admin in channel with Invite Users via Link Permission, Current Channel Value: {c}")
                err = True

        for c in FSUB:
            try:
                await self.get_chat(c)
                link = await self.create_chat_invite_link(c)
                FSUB_CHAT_LINKS[c] = link.invite_link
            except Exception as e:
               self.LOGGER(__name__).warning(e)
               self.LOGGER(__name__).warning(f"Please Double check the Channel id value and Make sure Bot is Admin in channel with Invite Users via Link Permission, Current Channel Value: {c}")
               err = True
        
        for c in PENDING_REQUEST:
            try:
                await self.get_chat(c)
                await self.helper_bot.get_chat(c)
                link = await self.create_chat_invite_link(c, creates_join_request=True)
                PENDING_REQUEST_LINKS[c] = link.invite_link
            except Exception as e:
                self.LOGGER(__name__).warning(e)
                self.LOGGER(__name__).warning(f"Please Double check the Channel id value and Make sure Bot is Admin in channel with Invite Users via Link Permission, Current Channel Value: {c}")
                err = True


        for c in set(BOT_ALL_CHANNELS):
            try:
                # Run both message tests in parallel
                tasks = [
                    self.send_message(chat_id=c, text="Test Message"),
                    self.helper_bot.send_message(chat_id=c, text="Test Message")
                ]
                test_messages = await asyncio.gather(*tasks)

                # Delete both messages in parallel
                delete_tasks = [msg.delete() for msg in test_messages]
                await asyncio.gather(*delete_tasks)
            except Exception as e:
                self.LOGGER(__name__).warning(e)
                self.LOGGER(__name__).warning(f"Please Double check the Channel id value and Make Sure Bot is Admin in channel, Current Value {c}")
                err = True
        
        if err:
            self.LOGGER(__name__).info("\nBOT STOPED..")
            sys.exit()
        
        # Start active bots from database
        try:
            managed_bots = await get_managed_bots()
            active_bots = [bot for bot in managed_bots if bot.get("is_active", False)]

            if active_bots:
                self.LOGGER(__name__).info(f"Starting {len(active_bots)} managed bots ...")
                start_tasks = [self.start_bot(bot["bot_token"]) for bot in active_bots]
                results = await asyncio.gather(*start_tasks, return_exceptions=True)

                # Process results
                for i, (bot, result) in enumerate(zip(active_bots, results)):
                    if isinstance(result, Exception):
                        self.LOGGER(__name__).warning(f"Failed to start bot @{bot['username']}: {str(result)}")
                        # Disable bot in database if it fails to start
                        await update_managed_bot(bot["bot_token"], False)
                    else:
                        success, msg = result
                        if success:
                            self.LOGGER(__name__).info(f"Started managed bot @{bot['username']}")
                        else:
                            self.LOGGER(__name__).warning(f"Failed to start bot @{bot['username']}: {msg}")
                            # Disable bot in database if it fails to start
                            await update_managed_bot(bot["bot_token"], False)
        except Exception as e:
            self.LOGGER(__name__).error(f"Error starting managed bots: {str(e)}")

        self.LOGGER(__name__).info(f"BOT RUNNING..")
        

    async def validate_token(self, token: str) -> bool:
        session_name = f"test_bot_{token.split(':')[0]}"
        if os.path.exists(f"{session_name}.session"):
            return False, "Bot Adding Is Already In Progress"
        try:
            test_client = Client(
                name=session_name,
                api_hash=API_HASH,
                api_id=API_ID, 
                bot_token=token
            )
            await test_client.start()
            await test_client.stop()
            # Cleanup session file
            if os.path.exists(f"{session_name}.session"):
                os.remove(f"{session_name}.session")
            return True, "success"
        except Exception as e:
            # Cleanup in case of error
            if os.path.exists(f"{session_name}.session"):
                os.remove(f"{session_name}.session")
            return False, str(e)

    async def verify_bot_channels(self, bot):
        """Verify bot access to channels and return missing channels"""
        missing_channels = []
        for c in BOT_ALL_CHANNELS:
            try:
                chat = await bot.get_chat(c)
                test = await bot.send_message(chat_id=c, text="Test Message")
                await test.delete()
            except Exception as e:
                missing_channels.append({
                    'chat_id': c,
                    'title': await self.get_chat_title(c)
                })
        return missing_channels

    async def get_chat_title(self, chat_id):
        """Get chat title safely"""
        try:
            chat = await self.get_chat(chat_id)
            return chat.title
        except:
            return str(chat_id)

    async def add_bot(self, token: str):
        if token in self.managed_bots:
            return False, "This BOT TOKEN Already Exists"

        success, msg = await self.validate_token(token)
        if not success:
            return False, f"Invalid BOT TOKEN or {msg}"

        session_name = f"temp_bot_{token.split(':')[0]}"
        temp_bot = Client(
            name=session_name,
            api_hash=API_HASH2,
            api_id=API_ID2,
            bot_token=token
        )
        try:
            await temp_bot.start()
            me = await temp_bot.get_me()
            missing_channels = await self.verify_bot_channels(temp_bot)
            await temp_bot.stop()
            
            # Cleanup session file
            if os.path.exists(f"{session_name}.session"):
                os.remove(f"{session_name}.session")
            
            # Always add bot to database with disabled status
            success = await add_managed_bot(token, me.username)
            if not success:
                return False, "Failed to add bot to database"
                
            # Return status with channel requirements if any
            if missing_channels:
                channels_text = "\n".join([f"• {c['title']} ({c['chat_id']})" for c in missing_channels])
                return True, f"BOT Successfully Add In DB But Join These Channels Before Start Using Bot.:\n {channels_text}"
            
            return True, "**BOT ADDED SUCCESSFULLY🔥\n>This Bot Is By-Default Disable**"
            
        except Exception as e:
            # Cleanup in case of error
            if os.path.exists(f"{session_name}.session"):
                os.remove(f"{session_name}.session")
            return False, f"Error Starting Bot: {str(e)}"

    async def set_bot_status(self, token: str, status: str):
        # Update database first
        success = await update_managed_bot(token, status == "active")
        if not success:
            return False, "Failed To Update Bot Status In DATABASE"
            
        if status == "active":
            # Start and add to managed_bots if enabling
            success, msg = await self.start_bot(token)
            if not success:
                await update_managed_bot(token, False)  # Revert database change
                return False, msg
        else:
            # Stop and remove from managed_bots if disabling
            await self.stop_bot(token)
            
        return True, f"Bot status updated to {status}"

    async def stop_bot(self, token: str):
        """Stop bot and remove from Managed bots"""
        if token in self.managed_bots:
            await self.managed_bots[token]['bot'].stop()
            del self.managed_bots[token]

    async def start_bot(self, token: str):
        if token in self.managed_bots:
            return True, "**Bot Already Running!! **"
            
        try:
            bot = Client(
                name=f"managed_bot_{token.split(':')[0]}",
                api_hash=API_HASH2,
                api_id=API_ID2,
                bot_token=token,
                plugins=dict(root="Stranger.plugins3"),
                workers=100
            )
            await bot.start()

            # Verify channels before starting
            missing_channels = await self.verify_bot_channels(bot)
            if missing_channels:
                await bot.stop()
                channels_text = "\n".join([f"• {c['title']} ({c['chat_id']})" for c in missing_channels])
                return False, f"Bot Needs Access To These Channels:\n> {channels_text}"
            
            me = await bot.get_me()
            self.managed_bots[token] = {
                'bot': bot,
                'token': token,
                'username': me.username,
                'status': "active"
            }
            return True, "Bot Started Successfully"
        except Exception as e:
            print(e)
            return False, f"Error starting bot: {str(e)}"

    async def remove_bot(self, token: str):
        if token in self.managed_bots:
            await self.managed_bots[token]['bot'].stop()
            del self.managed_bots[token]
            
        if os.path.exists(f"managed_bot_{token.split(':')[0]}.session"):
            os.remove(f"managed_bot_{token.split(':')[0]}.session")
        
        await remove_managed_bot(token)

    async def stop(self):
        for token in self.managed_bots:
            await self.managed_bots[token]['bot'].stop()
        await super().stop()


import sys
import asyncio
from pyrogram import Client

import config

from ..logger import LOGGER

assistants = []
assistantids = []


class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="StrangerXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            plugins=dict(root="Stranger.userbotPlugins"),
        )
        self.two = Client(
            name="StrangerXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )

    
    async def _setup_assistant(self, client:Client, assistant_num):
        """Setup an assistant client"""
        err = False
        try:
            await client.start()
        except Exception as e:
            print(e)
        assistants.append(assistant_num)
        
        
        client.id = client.me.id
        client.name = client.me.mention
        if not client.me.username:
            LOGGER(__name__).error(f"Please set username to {client.me.full_name} assistant and restart the bot again")
            sys.exit()
        client.username = client.me.username
        assistantids.append(client.id)
        LOGGER(__name__).info(f"Assistant {assistant_num} Started as {client.me.full_name}")
        
        return err

    async def start(self):
        if not (config.STRING1 or config.STRING2):
            LOGGER(__name__).error("No session string provided.")
            sys.exit()
        
        LOGGER(__name__).info("Starting Assistants...")
        
        tasks = []
        if config.STRING1:
            tasks.append(self._setup_assistant(self.one, 1))
        if config.STRING2:
            tasks.append(self._setup_assistant(self.two, 2))
        
        # Run all setup tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for any errors
        if any(isinstance(result, Exception) for result in results) or any(results):
            LOGGER(__name__).error("Encountered errors while starting assistants. Exiting.")
            sys.exit()

    async def stop(self):
        LOGGER(__name__).info("Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
        except:
            pass
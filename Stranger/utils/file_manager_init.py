"""
File Manager Integration for Stranger Bot

This module integrates the file manager with the main bot application.
It handles initialization and startup of the file management system.
"""

import asyncio
from Stranger.utils.file_manager import file_manager
from Stranger import LOGGER


async def init_file_manager():
    """Initialize file manager and resume pending tasks"""
    try:
        LOGGER(__name__).info("Initializing file manager...")
        
        # Resume any pending tasks from previous session
        await file_manager.resume_pending_tasks()
        
        LOGGER(__name__).info("File manager initialized successfully")
        
    except Exception as e:
        LOGGER(__name__).error(f"Error initializing file manager: {e}")


# This function should be called during bot startup
async def startup_file_manager():
    """Startup function for file manager"""
    await init_file_manager()

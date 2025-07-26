import sys
from motor.motor_asyncio import AsyncIOMotorClient as _mongo_client_
from pymongo import MongoClient
import config
from ..logger import LOGGER

if config.DB_URI is None:
    LOGGER(__name__).warning("No MONGO DB URL found.. Exiting.....")
    sys.exit()

_mongo_async_ = _mongo_client_(
    config.DB_URI,
    maxPoolSize=100,
    minPoolSize=10,
    maxIdleTimeMS=30000,
    connectTimeoutMS=5000,
    serverSelectionTimeoutMS=5000
    )
_mongo_sync_ = MongoClient(config.DB_URI)
mongodb = _mongo_async_[config.DB_NAME]
pymongodb = _mongo_sync_[config.DB_NAME]

LOGGER(__name__).info("DATABASE setup completed.")

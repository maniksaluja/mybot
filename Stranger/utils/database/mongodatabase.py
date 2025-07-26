import re
import pytz
import asyncio
import datetime
import functools
from enum import Enum
from typing import List, Dict, Any, TypedDict, Optional
import hashlib
import uuid

from motor.motor_asyncio import AsyncIOMotorCollection

from Stranger.core.mongo import mongodb
from Stranger.core.cache_config import (
    USER_CACHE, 
    CATEGORY_CACHE, 
    SETTINGS_CACHE, 
    CACHE_TTL
)
from Stranger import LOGGER
from config import emoji

import logging

async def is_cache_valid(cache_dict, key):
    """Check if cache entry exists and is valid"""
    return key in cache_dict

async def invalidate_cache(cache_dict, key=None):
    """Invalidate single key or entire cache"""
    if key:
        cache_dict.pop(key, None)
    else:
        cache_dict.clear()

def cache_with_timeout(cache_dict, timeout=CACHE_TTL):
    """Decorator for caching async function results"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            if await is_cache_valid(cache_dict, cache_key):
                logging.debug(f"Cache hit for {cache_key}")
                return cache_dict[cache_key]
            
            logging.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Only cache non-None results
            if result is not None:
                cache_dict[cache_key] = result
                # Schedule cache cleanup
                asyncio.create_task(clear_cache_after_timeout(cache_dict, cache_key, timeout))
                
            return result
        return wrapper
    return decorator

async def clear_cache_after_timeout(cache_dict, key, timeout):
    await asyncio.sleep(timeout)
    cache_dict.pop(key, None)

# Add local database for fast caching

sudoersdb = mongodb.sudoers
user_data = mongodb.users
linksdb=mongodb.linksdb # post links
category_countsdb = mongodb.category_counts
settingsdb = mongodb.settings
managed_botsdb = mongodb.managed_bots
pending_request = mongodb.pending_request
channel_files = mongodb.files # content links and other details
count = mongodb.count
bot_usersdb = mongodb.bot_users
payments = mongodb.payments
subscription = mongodb.subscription
token_store = mongodb.token
posts = mongodb.posts  # New collection for individual posts



# Sudoers
async def get_sudoers() -> list:
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    if not sudoers:
        return []
    return sudoers["sudoers"]

async def add_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True

async def remove_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True

#  user verification and privileges
class Plan(str, Enum):
    NONE = 'None'
    PLAN1 = 'plan1'
    PLAN2 = 'plan2'

class Subs_Type(str, Enum):
    NONE = 'None'
    TYPE1 = 'ads'
    TYPE2 = 'payment'
    TYPE3 = 'manual'

default_user_settings = {
    'is_token_verified': False,
    'token_expiry_time': 0,
    'token_verify_token': "",
    'is_download_verified': False,
    'download_expiry_time': 0,
    'download_verify_token': "",
    'is_banned': False,
    'download_plan': Plan.NONE,
    'token_plan': Plan.NONE,
    'access_token_type':Subs_Type.NONE,
    'access_download_type':Subs_Type.NONE,
}


async def get_user(user_id: int) -> Dict[str, Any]:
    """Get user settings with caching"""
    cached_user = USER_CACHE.get(user_id)
    if cached_user:
        return cached_user

    user = await user_data.find_one({'_id': user_id})
    if not user:
        user = {'_id': user_id, 'user_settings': default_user_settings}
        await user_data.insert_one(user)
    
    USER_CACHE[user_id] = user['user_settings']
    return user['user_settings']


async def set_user_field(user_id: int, field: str, value: Any) -> None:
    """Update user field and invalidate cache"""
    await user_data.update_one(
        {'_id': user_id},
        {'$set': {f'user_settings.{field}': value}},
        upsert=True
    )
    USER_CACHE.pop(user_id, None)


async def update_user(user_id: int, update:dict) -> None:
    """Update any user field"""
    await user_data.update_one(
        {'_id': user_id},
        {'$set': {'user_settings': update}},
        upsert=True
    )
    USER_CACHE.pop(user_id, None)


async def set_plan(user_id: int, plan_type: str, plan: Plan) -> None:
    """Set user plan (download or token)"""
    if not isinstance(plan, Plan):
        raise ValueError(f"Invalid plan. Must be one of {list(Plan)}")
    await set_user_field(user_id, f'{plan_type}_plan', plan)
    USER_CACHE.pop(user_id, None)

async def verify_token(user_id: int, token: str, token_type: str) -> bool:
    """Verify any token type"""
    stored = await get_user(user_id)
    if stored[f'{token_type}_verify_token'] == token:
        await set_user_field(user_id, f'is_{token_type}_verified', True)
        return True
    return False


async def manage_users(user_id: int, operation: str) -> None:
    """Manage user operations"""
    operations = {
        'add': lambda: user_data.insert_one({'_id': user_id, 'user_settings': default_user_settings}),
        'delete': lambda: user_data.delete_one({'_id': user_id}),
        'ban': lambda: set_user_field(user_id, 'is_banned', True),
        'unban': lambda: set_user_field(user_id, 'is_banned', False)
    }
    await operations[operation]()
    USER_CACHE.pop(user_id, None)

async def get_all_users() -> List[int]:
    """Get all users with details"""
    return [doc async for doc in user_data.find({}, {'_id': 1})]

async def user_exists(user_id: int) -> bool:
    """Check if user exists"""
    return bool(await user_data.find_one({'_id': user_id}))

async def get_banned_users() -> List[int]:
    """Get list of banned user IDs"""
    banned_users = [
        doc['_id'] 
        async for doc in user_data.find(
            {'user_settings.is_banned': True}, 
            {'_id': 1}
        )
    ]
    return banned_users

async def get_all_users_with_details() -> List[Dict[str, Any]]:
    """Get all users with their complete details including settings"""
    try:
        cursor = user_data.find({})
        users = []
        async for doc in cursor:
            user_details = {
                'user_id': doc['_id'],
                'settings': doc.get('user_settings', default_user_settings)
            }
            users.append(user_details)
        return users
    except Exception as e:
        print(f"Error fetching user details: {e}")
        return []

# Bot users

class BotUsers:
    def __init__(self, collection):
        self.bot_us = collection  # Collection to store bot-user relationships
    
    async def add_user(self, bot_username: str, user_id: int) -> bool:
        """Add user to bot's user list"""
        result = await self.bot_us.update_one(
            {'_id': bot_username},
            {'$addToSet': {'users': user_id}},
            upsert=True
        )
        return True

    async def del_user(self, bot_username: str, user_id: int) -> bool:
        """Remove user from bot's user list"""
        result = await self.bot_us.update_one(
            {'_id': bot_username},
            {'$pull': {'users': user_id}}
        )
        return result.modified_count > 0

    async def get_users(self, bot_username: str) -> list:
        """Get all users for a specific bot"""
        doc = await self.bot_us.find_one({'_id': bot_username})
        return doc['users'] if doc else []

    async def is_user(self, bot_username: str, user_id: int) -> bool:
        """Check if user exists in bot's user list"""
        doc = await self.bot_us.find_one(
            {'_id': bot_username, 'users': user_id}
        )
        return bool(doc)

bot_users = BotUsers(bot_usersdb)

# Auto generate settings

async def get_AG_settings():
    """Auto generate settings for the bot"""
    data = await settingsdb.find_one({'_id':'gen_type'})
    if data:
        return data['gen_type']
    else:
        return 'single'
    
async def set_AG_settings(gen_type:str):
    """Set auto generate settings for the bot"""
    return await settingsdb.update_one({'_id':'gen_type'}, {'$set':{'gen_type':gen_type}},upsert=True)

# functions for bot management
async def is_bot_exists(bot_token: str) -> bool:
    """Check if bot exists in managed bots database using token
    
    Args:
        bot_token (str): Bot token to check
        
    Returns:
        bool: True if bot exists, False otherwise
    """
    try:
        bot = await managed_botsdb.find_one({"bot_token": bot_token})
        return bool(bot)
    except Exception as e:
        print(f"Error checking bot existence: {str(e)}")
        return False

async def get_managed_bots() -> list:
    """Get all managed bot tokens"""
    cursor = managed_botsdb.find({})
    bots = []
    async for doc in cursor:
        bots.append({
            'bot_token': doc['bot_token'],
            'username': doc['username'],
            'is_active': doc.get('is_active', False)
        })
    return bots

async def add_managed_bot(token: str, username: str):
    data = {
        'bot_token': token,
        'username': username,
        'is_active': False,
    }
    try:
        await managed_botsdb.insert_one(data)
        return True
    except Exception as e:
        print(f"Error adding bot to database: {str(e)}")
        return False

async def update_managed_bot(token: str, is_active: bool):
    try:
        await managed_botsdb.update_one(
            {'bot_token': token},
            {'$set': {'is_active': is_active}}
        )
        return True
    except Exception as e:
        print(f"Error updating bot status: {str(e)}")
        return False

async def remove_managed_bot(bot_token: str) -> bool:
    """Remove a managed bot"""
    result = await managed_botsdb.delete_one({"bot_token": bot_token})
    return result.deleted_count > 0

# Auto approval settings

async def get_settings() -> dict:
    """Get settings with caching"""
    cached_settings = SETTINGS_CACHE.get('settings', None)
    if cached_settings:
        return cached_settings

    cursor = await settingsdb.find_one({'_id': 'settings'})
    default_settings = {
            'auto_approval': False,
            'welcome': False,
            'leave': False,
            'access_token': True,
            'payment_gateway': True,
            'downloads':True,
            'url_shortner': True,
            'thumbnail': False,
            'thumbnail_type': 'type1',
            'logs': True,
            'logs_type': 'logs1',
            'database_type':'type1',
            'promotion': False,
            'promotion_data': [
                {
                 "type": "text",
                "file_id": "", 
                "caption": "",
            }
            ]
        }
    if not cursor:
        await settingsdb.update_one(
            {'_id': 'settings'},
            {'$set': default_settings},
            upsert=True
        )
        SETTINGS_CACHE['settings'] = default_settings
        return default_settings

    settings = {
        key: cursor.get(key, default_settings[key])
        for key in default_settings
    }
    SETTINGS_CACHE['settings'] = settings
    return settings


async def update_settings(query:str, update:str):
    """Update auto approve settings"""
    await settingsdb.update_one(
        {'_id':'settings'},
        {"$set": {query : update}},
        upsert=True
        )
    SETTINGS_CACHE['settings'][query] = update

# Pending Request 
async def add_user_request(user_id: int, chat_id: int) -> bool:
    """Add user request to join chat"""
    try:
        await pending_request.insert_one({
            "user_id": user_id,
            "chat_id": chat_id,
        })
        return True
    except Exception:
        return False

async def remove_user_request(user_id: int, chat_id: int) -> bool:
    """Remove user request from chat"""
    try:
        result = await pending_request.delete_one({
            "user_id": user_id,
            "chat_id": chat_id
        })
        return result.deleted_count > 0
    except Exception:
        return False

async def is_user_requested(user_id: int, chat_id: int) -> bool:
    """Check if user has pending request for chat"""
    try:
        request = await pending_request.find_one({
            "user_id": user_id,
            "chat_id": chat_id
        })
        return request is not None
    except Exception:
        return False
    
async def clear_chat_requests(chat_id: int) -> bool:
    """Remove all pending requests for a specific chat"""
    try:
        result = await pending_request.delete_many({"chat_id": chat_id})
        return result.deleted_count > 0
    except Exception:
        return False
    
# File ids management

async def add_content(content_id: str, episode: int, promo_link = None) -> bool:
    """Create new content document with content_id and episode"""
    try:
        content_data = {
            "_id": content_id,
            "episode": episode,
            "contents": [],
            "promo_link": promo_link
        }
        await channel_files.insert_one(content_data)
        return True
    except Exception as e:
        print(f"Error adding content: {e}")
        return False

async def add_userbot_one_data(
    content_id: str,
    file_id: str,
    media_type: str,
    caption: str,
    msg_id: int,
    user_id: int
) -> tuple[bool, int]:
    """Add userbot_one_data to content and return success status with content index"""
    try:
        userbot_one_data = {
            "file_id": file_id,
            "media_type": media_type,
            "caption": caption,
            "msg_id": msg_id,
            "user_id": user_id
        }
        
        content_item = {
            "userbot_one_data": userbot_one_data,
            "userbot_two_data": {},
            "bot_data": {}
        }
        
        result = await channel_files.find_one_and_update(
            {"_id": content_id},
            {"$push": {"contents": content_item}},
            return_document=False 
        )
        
        if result:
            new_content_index = len(result.get("contents", []))
            return True, new_content_index
        else:
            return False, -1
            
    except Exception as e:
        print(f"Error adding userbot_one_data: {e}")
        return False, -1

async def add_userbot_two_data(
    content_id: str,
    content_index: int,
    msg_id: int,
    user_id: int
) -> bool:
    """Add userbot_two_data to specific content item"""
    try:
        userbot_two_data = {
            "msg_id": msg_id,
            "user_id": user_id
        }
        
        result = await channel_files.update_one(
            {"_id": content_id},
            {"$set": {f"contents.{content_index}.userbot_two_data": userbot_two_data}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error adding userbot_two_data: {e}")
        return False

async def add_bot_data(
    content_id: str,
    content_index: int,
    bot_id: str,
    file_id: str,
    media_type: str,
    caption: str,
    msg_id: int,
    chat_id: int
) -> bool:
    """Add bot_data to specific content item using bot_id as key"""
    try:
        bot_data = {
            "file_id": file_id,
            "media_type": media_type,
            "caption": caption,
            "msg_id": msg_id,
            "chat_id": chat_id
        }
        
        # Use $set to add/update bot data with bot_id as key
        result = await channel_files.update_one(
            {"_id": content_id},
            {"$set": {f"contents.{content_index}.bot_data.{bot_id}": bot_data}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error adding bot_data: {e}")
        return False

async def get_content(content_id: str) -> dict:
    """Get content document by content_id"""
    try:
        content = await channel_files.find_one({"_id": content_id})
        return content if content else None
    except Exception as e:
        print(f"Error getting content: {e}")
        return None

async def get_content_by_episode(episode: int) -> dict:
    """Get content document by episode number"""
    try:
        content = await channel_files.find_one({"episode": episode})
        return content if content else None
    except Exception as e:
        print(f"Error getting content by episode: {e}")
        return None

async def update_content_field(content_id: str, field: str, value: any) -> bool:
    """Update any field in content document"""
    try:
        result = await channel_files.update_one(
            {"_id": content_id},
            {"$set": {field: value}}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating content field: {e}")
        return False

async def delete_content(content_id: str) -> dict:
    """Delete content document and return deleted data"""
    try:
        content = await channel_files.find_one_and_delete({"_id": content_id})
        return content
    except Exception as e:
        print(f"Error deleting content: {e}")
        return None

async def get_latest_content_index(content_id: str) -> int:
    """Get the index of the latest content item (for adding userbot_two_data or bot_data)"""
    try:
        content = await channel_files.find_one({"_id": content_id})
        if content and "contents" in content:
            return len(content["contents"]) - 1
        return -1
    except Exception as e:
        print(f"Error getting latest content index: {e}")
        return -1

async def content_exists(content_id: str) -> bool:
    """Check if content exists"""
    try:
        content = await channel_files.find_one({"_id": content_id})
        return content is not None
    except Exception as e:
        print(f"Error checking content existence: {e}")
        return False

# Episode counter

class EpisodeCounter:
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection
        self.counter_id = "episode_counter"
    
    async def increment_episode(self) -> int:
        """Increment episode count by 1 using atomic operation"""
        try:
            result = await self.collection.find_one_and_update(
                {"_id": self.counter_id},
                {"$inc": {"count": 1}},
                upsert=True,
                return_document=True
            )
            return result["count"]
        except Exception as e:
            print(f"Error incrementing episode: {e}")
            return 0

    async def get_episode_count(self) -> int:
        """Get current episode count"""
        doc = await self.collection.find_one({"_id": self.counter_id})
        return doc["count"] if doc else 0

    async def reset_count(self) -> None:
        """Reset episode counter to zero"""
        await self.collection.delete_one({"_id": self.counter_id})

episode_counter = EpisodeCounter(count)

# Search function - Updated for new posts collection
async def search_channel_files(query: str) -> list:
    """
    Search across all categories in posts collection with enhanced matching
    Returns: List of unique matching posts with relevance scoring (score >= 5)
    """
    try:
        # Extract episode numbers from query with enhanced regex patterns
        episode_numbers = set()  # Use set to avoid duplicates
        
        # Multiple patterns to match different formats
        patterns = [
            r'episode[:\s]*(\d+)',  # matches: episode 50, episode:50
            r'episode[:\s]*(\d+)(?:\s*[,&]\s*episode[:\s]*(\d+))+',  # matches: episode 50 & episode 51
            r'episode[:\s]*(\d+)(?:\s*(?:and|&)\s*episode[:\s]*(\d+))+',  # matches: episode 50 and episode 51
            r'episode[:\s]*(\d+)(?:\s*[,&]\s*\d+)*'  # matches: episode 50, 51, 52
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, query.lower())
            for match in matches:
                # Add all captured groups
                episode_numbers.update(int(num) for num in match.groups() if num)
                # Also check for additional numbers in the match
                extra_numbers = re.findall(r'\d+', match.group())
                episode_numbers.update(int(num) for num in extra_numbers)
        
        episode_numbers = sorted(list(episode_numbers))  # Convert back to sorted list

        # Header text to ignore - updated for new format
        header = "┏━━━༺𝘍𝘈𝘕𝘉𝘢𝘴𝘦༻━━━┓\n☞ �𝘦𝘴𝘤𝘳𝘪𝘱𝘵𝘪𝘰𝘯 @UserHelpTG"

        pipeline = [
            # Clean caption by removing header
            {
                "$addFields": {
                    "cleaned_caption": {
                        "$replaceOne": {
                            "input": "$caption",
                            "find": header,
                            "replacement": ""
                        }
                    }
                }
            },
            # Match based on cleaned caption or episode numbers
            {
                "$match": {
                    "$or": [
                        {"cleaned_caption": {"$regex": query, "$options": "i"}},
                        *([{
                            "cleaned_caption": {
                                "$regex": f"𝘦𝘱𝘪𝘴𝘰𝘥𝘦.*?{num}\\b",
                                "$options": "i"
                            }
                        } for num in episode_numbers] if episode_numbers else [])
                    ]
                }
            },
            # Calculate relevance score
            {
                "$addFields": {
                    "relevance": {
                        "$add": [
                            # Episode match score
                            {
                                "$cond": {
                                    "if": {
                                        "$or": [
                                            *[{"$regexMatch": {
                                                "input": "$cleaned_caption",
                                                "regex": f"𝘦𝘱𝘪𝘴𝘰𝘥𝘦.*?{num}\\b",
                                                "options": "i"
                                            }} for num in episode_numbers]
                                        ] if episode_numbers else [{"$eq": [1, 1]}]
                                    },
                                    "then": 10,
                                    "else": 0
                                }
                            },
                            # Content match score
                            {
                                "$cond": {
                                    "if": {
                                        "$regexMatch": {
                                            "input": "$cleaned_caption",
                                            "regex": query,
                                            "options": "i"
                                        }
                                    },
                                    "then": 5,
                                    "else": 0
                                }
                            }
                        ]
                    }
                }
            },
            # Filter results with minimum relevance
            {
                "$match": {
                    "relevance": {"$gte": 5}
                }
            },
            # Project final results
            {
                "$project": {
                    "_id": 0,
                    "post_id": 1,
                    "category": 1,
                    "caption": 1,
                    "thumblink": 1,
                    "created_date": 1,
                    "date_str": 1,
                    "total_reactions": 1,
                    "relevance": 1
                }
            },
            # Sort by relevance and date
            {
                "$sort": {
                    "relevance": -1,
                    "created_date": -1
                }
            }
            # Removed the limit here to allow pagination
        ]

        cursor = posts.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        return results

    except Exception as e:
        print(f"Search error: {e}")
        print(f"Error details: {str(e)}")
        return []


# payments details

async def get_order_by_user_id(user_id):
    try:
        order = await payments.find_one({'user_id': user_id})
        return order if order else None
    except Exception as e:
        print(f"Error fetching order for user {user_id}: {e}")
        return None

async def get_user_payment_history(user_id: int, limit: int = 2):
    """Get user's payment history (last N orders) with payment and activation status"""
    try:
        cursor = payments.find(
            {'user_id': user_id}
        ).sort('createdAt', -1).limit(limit)
        
        orders = []
        async for order in cursor:
            payment_details = order.get('payment_details', {})
            order_details = order.get('order_details', {})
            
            # Check if paid based on the actual Razorpay webhook structure
            is_paid = False
            
            if payment_details and isinstance(payment_details, dict):
                # For Razorpay orders, check the payment_details structure
                payment_status = payment_details.get('status', '')
                amount_paid = payment_details.get('amount_paid', 0)
                
                # Check if status is 'paid' and amount_paid > 0
                if payment_status == 'paid' and amount_paid > 0:
                    is_paid = True
                
                # Also check if there are payments array with captured status
                payments_array = payment_details.get('payments', [])
                if payments_array and isinstance(payments_array, list):
                    for payment in payments_array:
                        if payment.get('status') == 'captured':
                            is_paid = True
                            break
                            
            elif order_details and isinstance(order_details, dict):
                # For Paytm orders, check order_details
                order_status_detail = order_details.get('orderStatus', '')
                is_paid = order_status_detail == 'TXN_SUCCESS'
            
            # Also check the main status field for backward compatibility
            order_status = order.get('status', 'PENDING')
            if order_status == 'SUCCESS':
                is_paid = True
            
            # Check if activated
            is_activated = order.get('activated', False)
            
            # Determine overall status based on payment_details
            overall_status = 'PENDING'
            if payment_details:
                razorpay_status = payment_details.get('status', 'created')
                if razorpay_status == 'paid':
                    overall_status = 'PAID'
                elif razorpay_status == 'expired':
                    overall_status = 'EXPIRED'
                elif razorpay_status == 'created':
                    overall_status = 'PENDING'
            elif order_status:
                overall_status = order_status
            
            order_info = {
                'order_id': order.get('orderId', ''),
                'amount': order.get('amount', 0),
                'subscription_type': order.get('subscription_type', ''),
                'plan_type': order.get('plan_type', ''),
                'status': overall_status,
                'is_paid': is_paid,
                'is_activated': is_activated,
                'created_at': order.get('createdAt', 0),
                'payment_details': payment_details,
                'order_details': order_details
            }
            orders.append(order_info)
        
        return orders
    except Exception as e:
        print(f"Error fetching payment history for user {user_id}: {e}")
        return []

async def create_order_data(order_data):
    result = await payments.insert_one(order_data)
    return result.inserted_id

async def update_order_data(order_id, status, qr_link, pay_url, updated_data):
    result = await payments.update_one(
        {'orderId': order_id},
        {'$set': {
            'status': status,
            'qr_link':qr_link,
            'pay_url':pay_url,
            'order_details':updated_data,
        }}
    )
    return result.modified_count > 0

async def update_order(order_id, query, data):
    result = await payments.update_one(
        {'orderId': order_id},
        {'$set': {query:data}}
        )
    

async def get_order_data(order_id):
    data = await payments.find_one({'orderId': order_id})
    return data


# Counting of subscription type

async def add_subscription(sub_type: str, plan: str, method: str, user_id: int):
    """Add subscription with details"""
    ist = pytz.timezone('Asia/Kolkata')
    await subscription.update_one(
        {
            "subscriptionType": sub_type,
            "planType": plan,
            "method": method
        },
        {
            "$inc": {"count": 1},
            "$addToSet": {"user_ids": user_id},
            "$push": {
                "history": {
                    "user_id": user_id,
                    "timestamp": datetime.datetime.now(ist)
                }
            }
        },
        upsert=True
    )

async def get_subscription_stats():
    """Get all subscription statistics with date range"""
    pipeline = [
        {
            "$project": {
                "subscriptionType": 1,
                "planType": 1,
                "method": 1,
                "count": {"$size": "$history"},
                "oldestDate": {"$min": "$history.timestamp"},
                "newestDate": {"$max": "$history.timestamp"}
            }
        }
    ]
    
    cursor = subscription.aggregate(pipeline)
    stats = {
        "subscriptions": {},
        "dateRange": {
            "oldest": None,
            "newest": None
        }
    }
    
    async for doc in cursor:
        key = f"{doc['subscriptionType']}_{doc['planType']}_{doc['method']}"
        stats["subscriptions"][key] = doc["count"]
        
        # Update global date range
        if doc.get("oldestDate"):
            if not stats["dateRange"]["oldest"] or doc["oldestDate"] < stats["dateRange"]["oldest"]:
                stats["dateRange"]["oldest"] = doc["oldestDate"]
        if doc.get("newestDate"):
            if not stats["dateRange"]["newest"] or doc["newestDate"] > stats["dateRange"]["newest"]:
                stats["dateRange"]["newest"] = doc["newestDate"]
    
    return stats

async def reset_all_subscriptions():
    result = await subscription.update_many(
        {},  # Empty filter matches all documents
        {
            "$set": {
                "count": 0,
                "user_ids": [],
                "history": []
            }
        }
    )
    return result

# token management

async def add_token_subscription( token: str, subscription_type: str, plan_type: str, method: str, order_id:str) -> bool:
    try:
        subscription_data = {
            "_id": token,
            "subscriptionType": subscription_type,
            "planType": plan_type,
            "method": method,
            "order_id": order_id
        }
        await token_store.insert_one(subscription_data)
        return True
    except Exception as e:
        print(f"Error adding token subscription: {str(e)}")
        return False

async def remove_token_subscription(token: str) -> bool:
    try:
        await token_store.delete_one({"_id": token})
        return True
    except Exception as e:
        print(f"Error removing token subscription: {str(e)}")
        return False

async def get_token_subscription(token: str) -> dict:
    try:
        result = await token_store.find_one({"_id": token})
        return result if result else {}
    except Exception as e:
        print(f"Error getting token subscription: {str(e)}")
        return {}

async def get_token_by_order_id(order_id: str) -> dict:
    try:
        result = await token_store.find_one({"order_id": order_id})
        return result if result else {}
    except Exception as e:
        print(f"Error getting token by order id: {str(e)}")
        return {}

# Enhanced daily reaction posts management
daily_reaction_posts = mongodb.daily_reaction_posts

async def save_daily_reaction_post(date_str: str, message_id: int, chat_id: int, 
                                 is_active: bool = True) -> bool:
    """Save daily reaction post with date-based key"""
    try:
        current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        await daily_reaction_posts.update_one(
            {"_id": date_str},
            {
                "$set": {
                    "message_id": message_id,
                    "chat_id": chat_id,
                    "is_active": is_active,
                    "created_at": current_time,
                    "last_updated": current_time
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"Failed to save daily reaction post for {date_str}: {e}")
        return False

async def get_daily_reaction_post(date_str: str) -> dict:
    """Get daily reaction post information for specific date"""
    try:
        data = await daily_reaction_posts.find_one({"_id": date_str})
        if data:
            return {
                "message_id": data.get("message_id"),
                "chat_id": data.get("chat_id"),
                "is_active": data.get("is_active", False),
                "created_at": data.get("created_at"),
                "last_updated": data.get("last_updated")
            }
        return None
    except Exception as e:
        return None

async def update_daily_reaction_post_activity(date_str: str, is_active: bool) -> bool:
    """Update daily reaction post activity status"""
    try:
        result = await daily_reaction_posts.update_one(
            {"_id": date_str},
            {
                "$set": {
                    "is_active": is_active,
                    "last_updated": datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
                }
            }
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"Failed to update daily reaction post activity for {date_str}: {e}")
        return False

async def get_active_daily_reaction_posts() -> list:
    """Get all active daily reaction posts"""
    try:
        cursor = daily_reaction_posts.find({"is_active": True})
        posts = []
        async for doc in cursor:
            posts.append({
                "date": doc["_id"],
                "message_id": doc.get("message_id"),
                "chat_id": doc.get("chat_id"),
                "created_at": doc.get("created_at"),
                "last_updated": doc.get("last_updated")
            })
        return posts
    except Exception as e:
        print(f"Failed to get active daily reaction posts: {e}")
        return []

async def cleanup_old_daily_reaction_posts(days_to_keep: int = 7) -> int:
    """Clean up old daily reaction posts (keep only last N days)"""
    try:
        cutoff_date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')) - datetime.timedelta(days=days_to_keep)
        cutoff_str = cutoff_date.strftime('%Y_%m_%d')
        
        result = await daily_reaction_posts.delete_many(
            {"_id": {"$lt": cutoff_str}}
        )
        return result.deleted_count
    except Exception as e:
        print(f"Failed to cleanup old daily reaction posts: {e}")
        return 0

# Daily prompt tracking (simplified for new system)

async def check_daily_prompt_needed(current_time) -> bool:
    """Check if user should be prompted to create daily post"""
    today_str = current_time.strftime('%Y_%m_%d')
    daily_prompt_doc = await settingsdb.find_one({'_id': f'daily_prompt_{today_str}'})
    return daily_prompt_doc is None

async def mark_daily_prompt_sent(current_time) -> None:
    """Mark that daily prompt has been sent for today"""
    today_str = current_time.strftime('%Y_%m_%d')
    await settingsdb.update_one(
        {'_id': f'daily_prompt_{today_str}'}, 
        {'$set': {'prompted': True, 'created_at': current_time}}, 
        upsert=True
    )

# NEW: Individual Posts Management with Per-Post Reactions

async def generate_post_id() -> str:
    """Generate unique post ID"""
    return str(uuid.uuid4())[:12]

async def add_post(category: str, caption: str, thumblink: str, content_id:str, 
                  created_date: datetime.datetime = None) -> str:
    """Add individual post with reaction structure"""
    if not created_date:
        ist = pytz.timezone('Asia/Kolkata')
        created_date = datetime.datetime.now(ist)
    
    post_id = await generate_post_id()
    
    # Initialize reaction structure
    reactions = {}
    reacted_users = {}
    for key in emoji.keys():
        if key.startswith('emoji_'):
            reactions[key] = 0
            reacted_users[key] = []
    
    post_doc = {
        'post_id': post_id,
        'content_id':content_id,
        'category': category,
        'caption': caption,
        'thumblink': thumblink,
        'created_date': created_date,
        'date_str': created_date.strftime('%Y_%m_%d'),
        'reactions': reactions,
        'reacted_users': reacted_users,
        'total_reactions': 0
    }
    
    await posts.insert_one(post_doc)
    return post_id

async def get_posts_by_category(category: str, limit: int = 50, 
                               date_filter: str = None) -> List[Dict]:
    """Get posts by category with optional date filtering"""
    query = {'category': category}
    
    if date_filter:
        query['date_str'] = date_filter
    
    cursor = posts.find(query).sort('created_date', -1).limit(limit)
    return [post async for post in cursor]

async def get_latest_posts(days: int = 1, limit: int = 50) -> List[Dict]:
    """Get latest posts from all categories within specified days"""
    ist = pytz.timezone('Asia/Kolkata')
    cutoff_date = datetime.datetime.now(ist) - datetime.timedelta(days=days)
    
    cursor = posts.find({
        'created_date': {'$gte': cutoff_date}
    }).sort('created_date', -1).limit(limit)
    
    return [post async for post in cursor]

async def get_posts_by_date(date_str: str, limit: int = 50) -> List[Dict]:
    """Get all posts for a specific date"""
    cursor = posts.find({
        'date_str': date_str
    }).sort('created_date', -1).limit(limit)
    
    return [post async for post in cursor]

async def get_post_by_content_id(content_id:str) -> Dict:
    """Get post by content_id"""
    return await posts.find_one({'content_id': content_id})

async def add_post_reaction(post_id: str, emoji_key: str, user_id: int) -> Dict:
    """Add reaction to specific post, prevent duplicate reactions from same user"""
    # First check if user already reacted with any emoji to this post
    post_doc = await posts.find_one({'post_id': post_id})
    if not post_doc:
        return None
    
    # Remove user from any previous reactions to this post
    update_remove = {}
    for key in post_doc['reacted_users']:
        if user_id in post_doc['reacted_users'][key]:
            update_remove[f'reacted_users.{key}'] = user_id
            # Decrement the reaction count for the old emoji
            await posts.update_one(
                {'post_id': post_id},
                {
                    '$pull': {f'reacted_users.{key}': user_id},
                    '$inc': {f'reactions.{key}': -1, 'total_reactions': -1}
                }
            )
    
    # Add new reaction
    result = await posts.update_one(
        {'post_id': post_id},
        {
            '$addToSet': {f'reacted_users.{emoji_key}': user_id},
            '$inc': {f'reactions.{emoji_key}': 1, 'total_reactions': 1}
        }
    )
    
    # Return updated reactions
    updated_post = await posts.find_one({'post_id': post_id})
    return updated_post if updated_post else None

async def get_post_reactions(post_id: str) -> Dict:
    """Get reaction data for specific post"""
    post_doc = await posts.find_one({'post_id': post_id}, {'reactions': 1})
    return post_doc['reactions'] if post_doc else {}

async def get_post_by_id(post_id: str) -> Dict:
    """Get complete post data by post_id"""
    return await posts.find_one({'post_id': post_id})

async def get_category_post_counts(date_str: str = None) -> Dict:
    """Get post counts by category for specific date or today"""
    if not date_str:
        ist = pytz.timezone('Asia/Kolkata')
        date_str = datetime.datetime.now(ist).strftime('%Y_%m_%d')
    
    pipeline = [
        {'$match': {'date_str': date_str}},
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}}
    ]
    
    results = posts.aggregate(pipeline)
    counts = {}
    async for result in results:
        counts[result['_id']] = result['count']
    
    return counts

async def delete_post(post_id: str) -> bool:
    """Delete a post by post_id"""
    try:
        result = await posts.delete_one({'post_id': post_id})
        return result.deleted_count > 0
    except Exception as e:
        LOGGER(__name__).error(f"Error deleting post {post_id}: {e}")
        return False
    
async def cleanup_user_seen_posts_for_deleted_post(post_id: str) -> bool:
    """Remove deleted post_id from all users' seen posts lists"""
    try:
        result = await user_seen_posts.update_many(
            {'seen_posts': post_id},
            {'$pull': {'seen_posts': post_id}}
        )
        return result.modified_count > 0
    except Exception as e:
        LOGGER(__name__).error(f"Error cleaning up seen posts for {post_id}: {e}")
        return False
       
# Aggregate reactions for daily posts
async def get_daily_reaction_aggregates(date_str: str = None) -> Dict:
    """Get aggregated reactions for all posts of a specific date"""
    if not date_str:
        ist = pytz.timezone('Asia/Kolkata')
        date_str = datetime.datetime.now(ist).strftime('%Y_%m_%d')
    
    pipeline = [
        {'$match': {'date_str': date_str}},
        {'$group': {
            '_id': None,
            **{f'total_{key}': {'$sum': f'$reactions.{key}'} 
               for key in emoji.keys() if key.startswith('emoji_')}
        }}
    ]
    
    result = await posts.aggregate(pipeline).to_list(1)
    if result:
        # Convert to expected format
        aggregated = {}
        for key in emoji.keys():
            if key.startswith('emoji_'):
                aggregated[key] = result[0].get(f'total_{key}', 0)
        return aggregated
    
    # Return zero counts if no data
    return {key: 0 for key in emoji.keys() if key.startswith('emoji_')}

# User seen posts tracking for new system
user_seen_posts = mongodb.user_seen_posts

async def get_user_seen_posts(user_id: int) -> List[str]:
    """Get list of post IDs the user has seen"""
    doc = await user_seen_posts.find_one({'user_id': user_id})
    return doc.get('seen_posts', []) if doc else []

async def add_user_seen_posts(user_id: int, post_ids: List[str]) -> bool:
    """Add post IDs to user's seen list"""
    await user_seen_posts.update_one(
        {'user_id': user_id},
        {'$addToSet': {'seen_posts': {'$each': post_ids}}},
        upsert=True
    )
    return True

async def clear_user_seen_posts(user_id: int) -> bool:
    """Clear user's seen posts list"""
    await user_seen_posts.delete_one({'user_id': user_id})
    return True

async def get_unseen_posts_for_user(user_id: int, category: str, limit: int = 10, 
                                   exclude_today: bool = True) -> List[Dict]:
    """Get unseen posts for user with efficient MongoDB aggregation pipeline"""
    try:
        # Get user's seen posts
        seen_posts = await get_user_seen_posts(user_id)
        
        # Build match query
        match_query = {'category': category}
        
        # Exclude user's seen posts
        if seen_posts:
            match_query['post_id'] = {'$nin': seen_posts}
        
        # Exclude today's content if requested
        if exclude_today:
            ist = pytz.timezone('Asia/Kolkata')
            today_str = datetime.datetime.now(ist).strftime('%Y_%m_%d')
            match_query['date_str'] = {'$ne': today_str}
        
        # Create aggregation pipeline
        pipeline = [
            {'$match': match_query},
            {'$sort': {'created_date': -1}},  # Latest first
            {'$limit': limit}
        ]
        
        # Execute pipeline
        cursor = posts.aggregate(pipeline)
        posts_found = [post async for post in cursor]
        
        # If we don't have enough posts, get additional random posts (even if seen before)
        if len(posts_found) < limit:
            remaining_needed = limit - len(posts_found)
            
            # Get already selected post IDs to exclude
            selected_post_ids = [post['post_id'] for post in posts_found]
            
            # Build query for additional posts
            additional_query = {
                'category': category,
                'post_id': {'$nin': selected_post_ids}  # Exclude already selected
            }
            
            if exclude_today:
                additional_query['date_str'] = {'$ne': today_str}
            
            # Get additional random posts
            additional_pipeline = [
                {'$match': additional_query},
                {'$sample': {'size': remaining_needed}},  # Random sampling
                {'$sort': {'created_date': -1}}
            ]
            
            additional_cursor = posts.aggregate(additional_pipeline)
            additional_posts = [post async for post in additional_cursor]
            
            posts_found.extend(additional_posts)
        
        return posts_found
    
    except Exception as e:
        LOGGER(__name__).error(f"Error in get_unseen_posts_for_user: {e}")
        return []

async def get_random_unseen_posts_for_user(user_id: int, limit: int = 10, 
                                          exclude_today: bool = True) -> List[Dict]:
    """Get random unseen posts from all categories with efficient MongoDB aggregation"""
    try:
        # Get user's seen posts
        seen_posts = await get_user_seen_posts(user_id)
        
        # Build match query for all categories
        categories = ["indian", "global", "dark", "others"]
        match_query = {'category': {'$in': categories}}
        
        # Exclude user's seen posts
        if seen_posts:
            match_query['post_id'] = {'$nin': seen_posts}
        
        # Exclude today's content if requested
        if exclude_today:
            ist = pytz.timezone('Asia/Kolkata')
            today_str = datetime.datetime.now(ist).strftime('%Y_%m_%d')
            match_query['date_str'] = {'$ne': today_str}
        
        # Create aggregation pipeline for random unseen posts
        pipeline = [
            {'$match': match_query},
            {'$sample': {'size': limit * 2}},  # Get more posts for better randomness
            {'$sort': {'created_date': -1}},   # Sort by latest first
            {'$limit': limit}
        ]
        
        # Execute pipeline
        cursor = posts.aggregate(pipeline)
        posts_found = [post async for post in cursor]
        
        # If we don't have enough posts, get additional random posts (even if seen before)
        if len(posts_found) < limit:
            remaining_needed = limit - len(posts_found)
            
            # Get already selected post IDs to exclude
            selected_post_ids = [post['post_id'] for post in posts_found]
            
            # Build query for additional posts
            additional_query = {
                'category': {'$in': categories},
                'post_id': {'$nin': selected_post_ids}  # Exclude already selected
            }
            
            if exclude_today:
                additional_query['date_str'] = {'$ne': today_str}
            
            # Get additional random posts
            additional_pipeline = [
                {'$match': additional_query},
                {'$sample': {'size': remaining_needed}},  # Random sampling
                {'$sort': {'created_date': -1}}
            ]
            
            additional_cursor = posts.aggregate(additional_pipeline)
            additional_posts = [post async for post in additional_cursor]
            
            posts_found.extend(additional_posts)
        
        return posts_found
    
    except Exception as e:
        LOGGER(__name__).error(f"Error in get_random_unseen_posts_for_user: {e}")
        return []

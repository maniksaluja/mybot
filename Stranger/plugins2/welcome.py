from pyrogram import Client, filters
from pyrogram.types import ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup,ChatMemberUpdated
from pyrogram.errors import (PeerIdInvalid,
                             UserAlreadyParticipant, UserIsBlocked, UserIsBot)
from pyrogram.enums import ChatMemberStatus

from Stranger import app
from Stranger.utils.database.mongodatabase import add_user_request, remove_user_request
from config import JOIN_IMAGE, RFSUB_CHATS, PENDING_REQUEST,LEAVE_VOICE,RFSUB_CHAT_LINKS, FSUB_CHAT_LINKS, PENDING_REQUEST_LINKS
from Stranger.logger import LOGGER
from Stranger.utils.database import get_settings, bot_users
from strings import JOIN_MESSAGE, TUTORIAL_LINK, MUST_VISIT_LINK, LEAVE_MESSAGE

PEND = filters.chat()
for chat in PENDING_REQUEST:
    PEND.add(chat)

@Client.on_chat_join_request(PEND)
async def pending_requests(_,join_request:ChatJoinRequest):
    user = join_request.from_user.id
    chat = join_request.chat.id
    await add_user_request(user,chat)

@Client.on_chat_join_request(RFSUB_CHATS)
async def accept_join_request(client, join_request:ChatJoinRequest):
    user = join_request.from_user.id
    chat = join_request.chat.id
    await add_user_request(user, chat)
    settings = await get_settings()
    if not settings['auto_approval']:
        return
    try:
        await join_request.approve()
        return await remove_user_request(user, chat)
    except UserAlreadyParticipant:
        pass
    except Exception as e:
        LOGGER(__name__).error(f"Error: {e}")


@Client.on_chat_member_updated(RFSUB_CHATS)
async def welcome_leave(client:Client, update:ChatMemberUpdated):
    if update.new_chat_member:
        user = update.new_chat_member.user
        chat = update.chat.id
        await remove_user_request(user.id, chat)

    settings = await get_settings()
    
    if update.new_chat_member and update.new_chat_member.status != ChatMemberStatus.BANNED:
        user = update.new_chat_member.user
        if not settings["welcome"]:
            return
        button = InlineKeyboardMarkup(
          [
            [
              InlineKeyboardButton("sᴇɴᴅ ᴊᴏɪɴ ʀᴇϙ", url="https://t.me/+b8C17GC49zYxMTg1"), #JoinBackUp
              InlineKeyboardButton("ᴠɪsɪᴛ ᴍᴜsᴛ", url=MUST_VISIT_LINK), #VisitMust
            ],
            [
              InlineKeyboardButton("ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴛᴇʀᴀʙᴏx ʙᴏᴛ", url=TUTORIAL_LINK)
            ]
          ]
        )

        try:
            if JOIN_IMAGE:
                await client.send_photo(user.id, JOIN_IMAGE, caption=JOIN_MESSAGE.format(user.mention), reply_markup=button,disable_notification=True)
            else:
                await client.send_message(user.id, JOIN_MESSAGE.format(user.mention), reply_markup=button,disable_notification=True)
            
            await bot_users.add_user(app.helper_bot_username, user.id)
        except PeerIdInvalid:
            LOGGER(__name__).info(f"user id invalid {user.id}")
        except UserIsBlocked:
            pass
        except UserIsBot:
            pass
        except Exception as e:
            LOGGER(__name__).error(f"Error: {e}")
    elif update.old_chat_member and update.old_chat_member.status != ChatMemberStatus.BANNED:
        if not settings["leave"]:
            return
        user = update.old_chat_member.user
        temp = {**RFSUB_CHAT_LINKS, **FSUB_CHAT_LINKS, **PENDING_REQUEST_LINKS}
        link = temp[update.chat.id]
        button = InlineKeyboardMarkup(
          [
            [
              InlineKeyboardButton("ᴊᴏɪɴ ᴀɢᴀɪɴ", url=link),
              InlineKeyboardButton("ᴠɪsɪᴛ ᴍᴜsᴛ", url=MUST_VISIT_LINK)
            ],
            [
              InlineKeyboardButton("ʜᴏᴡ ᴛᴏ ᴜsᴇ ᴛᴇʀᴀʙᴏx ʙᴏᴛ", url=TUTORIAL_LINK)
            ]
          ]
        )
        try:
            return await client.send_voice(user.id, LEAVE_VOICE, caption=LEAVE_MESSAGE, reply_markup=button, disable_notification=True)
        except PeerIdInvalid:
            LOGGER(__name__).info(f"Peer id invalid {user.id}")
        except UserIsBlocked:
            pass
        except UserIsBot:
            pass
        except Exception as e:
            LOGGER(__name__).error(f"Error: {e}")
        

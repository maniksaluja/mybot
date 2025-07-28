import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPrivileges
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from pyrogram.errors import FloodWait

from Stranger import app, userbot
from Stranger.misc import SUDOERS
from Stranger.logger import LOGGER

@app.on_message(filters.command("pending") & SUDOERS)
async def pending(_, message: Message):
    if len(message.command) < 2 or len(message.command) > 3:
        return await message.reply("Usage: /pending [group/channel id] [no of users to accept(optional)]")
    
    if len(message.command) == 3:
        group_id = int(message.command[1])
        num = int(message.command[2])
    else:
        group_id = int(message.command[1])
        num = 9999999999

    try:
        wait = await app.get_chat(group_id)
        is_group = wait.type in (ChatType.GROUP, ChatType.SUPERGROUP)
    except Exception as e:
        return await message.reply(f">**Invalid Channel/group ID or Bot Has Not Access To The Group/Channel** .\nError: {e}")
    
    temp_msg = await message.reply("**Its Take Some Time Under Processing...**")
    try:
        try:
            member = await app.get_chat_member(group_id, userbot.one.id)
        except UserNotParticipant:
            is_member = False
            member = None
        except Exception as e:
            member = None
            LOGGER(__name__).info(f"Error : {e}")

        is_member = member and member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER)
        if not is_member: 
            group_link = wait.invite_link
            await userbot.one.join_chat(group_link)
        await asyncio.sleep(2)
        is_owner_or_admin = bool(member and member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR))
        if not is_owner_or_admin:
            if is_group:
                await app.promote_chat_member(
                    chat_id=group_id,
                    user_id=userbot.one.id,
                    privileges=ChatPrivileges(
                        can_change_info=True,
                        can_invite_users=True,
                        can_delete_messages=True,
                        can_restrict_members=True,
                        can_pin_messages=True,
                        can_promote_members=True,
                        can_manage_chat=True,
                        can_manage_video_chats=True,
                    )
            )
            else:
                await app.promote_chat_member(
                    chat_id=group_id,
                    user_id=userbot.one.id,
                    privileges=ChatPrivileges(
                        can_manage_chat=True,
                        can_delete_messages=True,
                        can_restrict_members=True,
                        can_change_info=True,
                        can_post_messages=True,
                        can_edit_messages =True,
                        can_invite_users=True,
                        )
                )
        if member and member.status == ChatMemberStatus.ADMINISTRATOR:
            if not member.privileges.can_invite_users:
                return await temp_msg.edit(f"**The userbot {userbot.one.name} Has Not permissions To Accept Requests**")

        pending_requests = userbot.one.get_chat_join_requests(group_id)
        count = 0
        async for member in pending_requests:
            if count == num:
                break
            try:
                if member.pending:
                    await app.helper_bot.approve_chat_join_request(group_id, member.user.id)
                    await asyncio.sleep(1)
                    count += 1
            
                if count % 10 == 0:
                        await temp_msg.edit(f"**Progress: Accepted {count} Pending Requests So Far..**.")
            except FloodWait as fw:
                await asyncio.sleep(int(fw.x))
                if member.pending:
                    await app.helper_bot.approve_chat_join_request(group_id, member.user.id)
                    await asyncio.sleep(1)
                    count += 1
            
                if count % 10 == 0:
                        await temp_msg.edit(f"**Progress: Accepted {count} Pending Requests So Far..**.")
            except:
                try:
                    await userbot.one.approve_chat_join_request(group_id, member.user.id)
                    await asyncio.sleep(1)
                    count += 1
                except:
                    pass
                pass

        return await temp_msg.edit("**Pending Requests Accepted \n>Total Accepted:** `{}`".format(count))
    except Exception as e:
        LOGGER(__name__).info(f"Something Went Wrong While Approving Join Requests: {e}")
        return await temp_msg.edit(f"**Error Occured While Accepting Pending Requests**\n\n **Error:** {str(e)}")
        
        
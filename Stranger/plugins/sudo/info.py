import os
import time
import psutil
import platform
import speedtest
from pyrogram import Client, filters, __version__
from pyrogram.types import Message

from Stranger import app
from Stranger.misc import SUDOERS, __boot__
from Stranger import LOGGER
from Stranger.utils.helper import get_readable_time
from config import INFO_PIC 

@app.on_message(filters.command("info") & SUDOERS)
async def get_info(client: Client, message: Message):
    """Get system information."""
    # Send initial message
    msg = await message.reply_text("Gathering system information...",disable_notification=True)
    
    # CPU Info
    cpu_freq = psutil.cpu_freq().current
    cpu_cores = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent()
    
    # RAM Info
    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024 ** 3)  # Convert to GB
    ram_total = ram.total / (1024 ** 3)
    
    # Storage Info
    disk = psutil.disk_usage('/')
    storage_total = disk.total / (1024 ** 3)
    storage_used = disk.used / (1024 ** 3)
    storage_free = disk.free / (1024 ** 3)
    
    # Internet Speed Test
    result = None
    download_speed = upload_speed = 0
    ping = "N/A"
    country = "N/A"
    country_code = "N/A"
    
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        st.download()
        st.upload()
        st.results.share()
        result = st.results.dict()
        download_speed = result['download'] / (1024 ** 2)
        upload_speed = result['upload'] / (1024 ** 2)
        ping = result['ping']
        country = result['server']['country']
        country_code = result['server']['cc']
    except Exception as e:
        LOGGER(__name__).info(f"Error occurred in speed test: {e}")
    
    # System Info
    python_version = platform.python_version()
    pyrogram_version = __version__
    os_info = platform.system() + " " + platform.release()

    bot_uptime = get_readable_time(time.time() - __boot__)
    
    # Format the message
    info_text = f"""
**System Information**
• **Platform :__{os_info}__**
• **CPU Cores : __{cpu_cores}__**
• **CPU Usage : __{cpu_percent}%__**
• **RAM Usage : __{ram_total:.2f}GB {(ram_used*100)/ram_total:.2f}%__**
• **Storage Usage : __{storage_total:.2f}GB {(storage_used*100)/storage_total:.2f}%__**
• **Bot Uptime : __{bot_uptime}__**
• **Country : __{country}, {country_code}__**

**Network Speed**
• **Download : __{download_speed:.2f} Mbps __**
• **Upload : __{upload_speed:.2f} Mbps __**
• **Ping : __{ping}__**
  
**Software Versions**
• **Python : __{python_version}__**
• **Pyrogram : __{pyrogram_version}__**
"""
    await msg.delete()
    return await message.reply_photo(
        photo=INFO_PIC,
        caption=info_text,
        quote=True
    )
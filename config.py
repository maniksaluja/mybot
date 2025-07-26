
import re
import sys
import os
import base64
import struct
from os import getenv
from pyrogram import filters
from dotenv import load_dotenv

load_dotenv()

# API CONFIGURATION 
API_ID = int(getenv("API_ID", "28070245"))
API_ID2 = int(getenv("API_ID2", "20886865"))

#API HASH CONFIGURATION 
API_HASH = getenv("API_HASH", "c436fc81a842d159c75e1e212b7f6e7c")
API_HASH2 = getenv("API_HASH2", "754d23c04f9244762390c095d5d8fe2b")

#MAIN/POSTING BOT TOKEN
BOT_TOKEN = getenv("BOT_TOKEN", "7618200137:AAEyzO_yPPIWwHNpjDCvctiicJuUbhwQ2Mg")
#HELPER & WELCOME BOT TOKEN
BOT_TOKEN2 = getenv("BOT_TOKEN2","8232557277:AAHTX7U2t8JpWTPwVRUHk41Q3LmGT73gyvU")

OWNER_ID = list(
    map(int, getenv("OWNER_ID", "7528489965").split())
)


#USERBOTS FOR DATABASE BACK-UP 
STRING1=getenv("STRING_SESSION", "BAG9XXgAH4D4Uj1w2SPR-VFiSNh9sYu_6rlbB7D0tjlB2rHQyouvN0VXria_9_H6SucwJV6JZdqP46yA-ZNUNwjH-9ll3NMOiaXLTCnrwy3CsD2TugFY02KOD-mucXzUQnvONQAlGxs1y2fx95wodTEtNxGVPxuX99lfytHuWgAlyFqab9-vUSM7ZFksiosmLosXNciC8mqPLFSvPCvxczWTTRmxWmylx9Xr-0UEKbJViCYGT71OFR3zOAsVRxR4lAeAwDrGEUO30Aen0jFtoBp9O13dhuOLgArL5WAZweqH2NgTEAgJEjzyMGtAX6oX9AVWsolNNPw3GWAfqHwvUl4iJiEcTQAAAAHn80bwAA")
STRING2 =getenv("STRING_SESSION2" , "BAHCtg8AmmbE5aerOoZ0h-FF2xRSRs8WFitRQ4SLvOehdVUR5Ynki7z_GeE2UGgLjiO0I5NPneZR6tCeLEo1_IqLqmYwNIoqsB4iiJuSHDGje3LL3Nmtt3e_9DryyKc-d2U8JtKwrcvqveHF89bed0cpCyvhat56S6vcagUGug3WYxjOiHIolnHoT4jZZJ_U9KvIB1wfDWr3iAkJzYPKjG124hNhuwz2C37UbhPPw2nF68EH4o7x5AoIn3nRcCoIr2e6ccKWC2x9gj1FSIb2qPqI0ik2_8_Pd_hfmQ4bZ0NIua1zwtO9bjO7sSVunncABDsaYUAgWuKzuv3_qjS25059z98e-wAAAAG5yRgIAA")


LOGS_CHANNEL_1 = int(getenv("LOGS_CHANNEL_1",-1002734592501))
LOGS_CHANNEL_2 = int(getenv("LOGS_CHANNEL_2",-1002734592501))
BCAST_CHANNEL = int(getenv("BCAST_CHANNEL", -1002734592501)) 
#☝🏻This is important to keep communication between the bots☝🏻

#ADMIN CONVENTION CHANNEL 
USELESS_CHANNEL = int(getenv("USELESS_CHANNEL", -1002734592501))
#SHARE & CARE CHANNEL ID
FEEDBACK_CHANNEL = int(getenv("FEEDBACK_CHANNEL",-1002734592501))

#MOMGO DATABASE URL HERE
DB_URI = getenv("DATABASE_URL", "mongodb+srv://shanaya:godfather11@cluster0.t3yd7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME = getenv("DATABASE_NAME", "sparrow_v2")

#SET YOUR FSUB EXAMPLE = {-1002341255671:"PENDING1" , -1002273566865: "PENDING2"} , KEEP IT MT {} FOR DISABLE 
RFSUB = {-1002565558833:"𝘈𝘯𝘯𝘰𝘶𝘯𝘤𝘦𝘮𝘦𝘯𝘵 "}
FSUB = {}
PENDING_REQUEST = {-1002713988969:"𝘚𝘦𝘯𝘥 𝘑𝘰𝘪𝘯 𝘙𝘦𝘲"}

#REACTION CHANNEL FOR REACTION POST
REACTION_CHANNEL = int(getenv("REACTION_CHANNEL", -1002565558833))

#ADD PAYTM API KEY FORM  WEBSITE FOR GETWAY 
PAYTM_API_KEY = getenv("PAYTM_API_KEY","eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJuYW1lIjoic3BhcnJvdyIsImVtYWlsIjoibWF1OWFtYW5AZ21haWwuY29tIiwiaWQiOjR9.gBANLqch_xNuRFmIVIt4Gn5G4_PgV9dX3OvSoN_yoPQ")

# RAZORPAY WEBHOOK CONFIGURATION
RAZORPAY_WEBHOOK_SECRET = getenv("RAZORPAY_WEBHOOK_SECRET", "sparrowtest")
WEBHOOK_URL = getenv("WEBHOOK_URL", "https://web.tgbox.fun")

# YOU CAN ADD YOUR URL SHORTNUER
SHORTLINK_URL = getenv("SHORTLINK_URL", "shortner.in")
SHORTLINK_API = getenv("SHORTLINK_API", "d6367d8367eb3017e04fbe38fa182aceb5d92c80")

#SET AUTO DELETE TIMER IN SEC , KEEP IT 0 FOR DISABLE
AUTO_DELETE_CONTENT = int(getenv('AUTO_DELETE_CONTENT', 7200)) #Sec
AUTO_DELETE_POST = int(getenv("AUTO_DELETE_POST" , 60*60*2)) #HRS


# SET DAILY LIMIT, IF ACCESSKEY MODE ENABLE 
DAILY_FREE_CONTENT = int(getenv("DAILY_FREE_CONTENT",5))
MAX_POSTS = 10
FIND_SEARCH_TIMEOUT = 600

#YOJ CAN CUSTOMIZE ACCESSKEY PLAN 1 PRICE & DUTRTON 
ACCESS_TOKEN_PLAN_1 = int(getenv("ACCESS_TOKEN_PLAN_1" , 60*60*24)) # 1 day
ACCESS_TOKEN_PLAN_1_PRICE = int(getenv("ACCESS_TOKEN_PLAN_1_PRICE", 2)) 

#YOJ CAN CUSTOMIZE ACCESSKEY PLAN 2  PRICE & DUTRTON 
ACCESS_TOKEN_PLAN_2 = int(getenv("ACCESS_TOKEN_PLAN_2" , 60*60*24*30)) # 30 days
ACCESS_TOKEN_PLAN_2_PRICE = int(getenv("ACCESS_TOKEN_PLAN_2_PRICE", 12))

#restricted Type For MultipleBot True/False
PROTECT_CONTENT = True

#YOU CAN CUSTOMIZE DOWNLOAD PAN 1 PRICE & DUTRTON 
DOWNLOAD_PLAN_1 = int(getenv("DOWNLOAD_PLAN_1" , 60*60*10)) # 10 hours
DOWNLOAD_PLAN_1_PRICE = int(getenv("DOWNLOAD_PLAN_1_PRICE", 9))

#YOU CAN CUSTOMIZE DOWNLOAD PLAN 2 PRICE & DUTRTON 
DOWNLOAD_PLAN_2 = int(getenv("DOWNLOAD_PLAN_2" , 60*60*24*30)) # 30 days 
DOWNLOAD_PLAN_2_PRICE = int(getenv("DOWNLOAD_PLAN_2_PRICE", 11))


THUMBNAIL_PIC_1 = getenv("THUMBNAIL_PIC_1", "https://graph.org/file/e677ea79ecbdae5b8dbaa.jpg")
THUMBNAIL_PIC_2 = getenv("THUMBNAIL_PIC_2", "https://graph.org/file/5f3d0d2c8e35a037e4663.jpg")


# ================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================================
### DONT TOUCH or EDIT codes after this line

BANNED_USERS = filters.user()
LOG_FILE_NAME = "Strangerlogs.txt"
RFSUB_CHAT_LINKS={}
FSUB_CHAT_LINKS={}
PENDING_REQUEST_LINKS={}
RFSUB_CHATS = filters.chat()
for chat_id in RFSUB:
    RFSUB_CHATS.add(chat_id)


temp = {**RFSUB, **FSUB, **PENDING_REQUEST}
temp_channels = [key for key in temp]
ALL_CHANNELS = temp_channels
BOT_ALL_CHANNELS = [x for x in temp_channels]

BOT_ALL_CHANNELS.append(LOGS_CHANNEL_1)
BOT_ALL_CHANNELS.append(LOGS_CHANNEL_2)
BOT_ALL_CHANNELS.append(USELESS_CHANNEL)
BOT_ALL_CHANNELS.append(FEEDBACK_CHANNEL)

TOKEN_SECRET_EXPIRY_TIME =86400
# EMOJI FOR REACTION, YOU CAN ADD MULTIPLE REACTIONS

emoji = {
    "emoji_1":"👍🏻",
    "emoji_2":"❤️",
    "emoji_3":"😂",
    "emoji_4":"🤤",
    "emoji_5":"👎🏻",
    "emoji_6":"💔",
    "emoji_7":"😭",
    "emoji_8":"🤬",
}

PAYMENT_HOST = "https://api-pay.wansaw.com/"

BASE_GIF = getenv(
    "BASE_GIF",
    "assets/base.gif.mp4",
)

BASE_IMAGE = getenv(
    "BASE_IMAGE",
    "assets/base_pic.jpg",
    )


START_GIF = getenv(
    "START_GIF",
    "assets/start.gif.mp4",
    )
START_IMG = getenv(
    "START_IMG",
    "assets/START_IMG.jpg",
)

DOWNLOAD_AUDIO = getenv(
    "DOWNLOAD_AUDIO",
    "assets/download_audio.ogg",
)
WARNING_AUDIO = getenv(
    "WARNING_AUDIO",
    "assets/warning_audio.ogg",
)

IMPORTANT_AUDIO = getenv(
    "IMPORTANT_AUDIO",
    "assets/SendRequest.ogg"
)

JOIN_IMAGE = getenv(
    'JOIN_IMAGE',
    'assets/join_image.jpg'
    )

LEAVE_VOICE = getenv(
    "LEAVE_VOICE",
    "assets/leave_voice.ogg"
)

INFO_PIC = getenv(
    "INFO_PIC",
    "assets/info_pic.jpg",
)

PAYMENT_THUMBNAIL = "assets/payment_thumbnail.jpg" if os.path.exists("assets/payment_thumbnail.jpg") else None
MB_USELESS_THUMBNAIL = "assets/mb_useless_thumbnail.jpg" if os.path.exists("assets/mb_useless_thumbnail.jpg") else None

# File path for the SQLite database
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DATA_DIR, "seen_posts.db")

if BASE_GIF:
    if BASE_GIF != "assets/base.gif.mp4":
        if not re.match("(?:http|https)://", BASE_GIF):
            print(
                "[ERROR] - Your BASE_GIF url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if BASE_IMAGE:
    if BASE_IMAGE != "assets/base_pic.jpg":
        if not re.match("(?:http|https)://", BASE_IMAGE):
            print(
                "[ERROR] - Your BASE_IMAGE url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if START_GIF:
    if START_GIF != "assets/start.gif.mp4":
        if not re.match("(?:http|https)://", START_GIF):
            print(
                "[ERROR] - Your START_GIF url is wrong. Please ensure that it starts with https://"
                )
            sys.exit()

if START_IMG:
    if START_IMG != "assets/START_IMG.jpg":
        if not re.match("(?:http|https)://", START_IMG):
            print(
                "[ERROR] - Your START_IMG url is wrong. Please ensure that it starts with https://"
            )
            sys.exit()

if DOWNLOAD_AUDIO:
    if DOWNLOAD_AUDIO != "assets/download_audio.ogg":
        print(
            "[ERROR] - Your Download audio name is invalid."
            )
        sys.exit()

if WARNING_AUDIO:
    if WARNING_AUDIO != "assets/warning_audio.ogg":
        print(
            "[ERROR] - Your warning audio name is invalid."
            )
        sys.exit()

if IMPORTANT_AUDIO:
    if IMPORTANT_AUDIO != "assets/SendRequest.ogg":
        print(
            "[ERROR] - Your important audio name is invalid."
            )
        sys.exit()
        
if JOIN_IMAGE:
    if JOIN_IMAGE != "assets/join_image.jpg":
        if not re.match("(?:http|https)://", JOIN_IMAGE):
            print(
                "[ERROR] - Your JOIN_IMAGE url is wrong. Please ensure that it starts with https://"
                )
            sys.exit()

if LEAVE_VOICE:
    if LEAVE_VOICE != "assets/leave_voice.ogg":
        print("[ERROR] - Your leave voice name is invalid.")
        sys.exit()

if INFO_PIC:
    if INFO_PIC != "assets/info_pic.jpg":
        if not re.match("(?:http|https)://", INFO_PIC):
            print(
                "[ERROR] - Your INFO_PIC url is wrong. Please ensure that it starts with https")
            sys.exit()
            

MULTIPLE_BOT_ALLOWED_DM = filters.user()

if STRING1:
    _, _, _, _, user_id, _ = struct.unpack(
            ">BIB256sQB",
            base64.urlsafe_b64decode(STRING1 + "=" * (-len(STRING1) % 4))
            )
    MULTIPLE_BOT_ALLOWED_DM.add(int(user_id))

if STRING2:
    _, _, _, _, user_id, _ = struct.unpack(
            ">BIB256sQB",
            base64.urlsafe_b64decode(STRING2 + "=" * (-len(STRING2) % 4))
            )
    MULTIPLE_BOT_ALLOWED_DM.add(int(user_id))

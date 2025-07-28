"""
Simple webhook server for handling Razorpay payment notifications using FastAPI
"""
import json
import time
import asyncio
import pytz
import uvicorn
import datetime
import requests
import queue
import threading
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from Stranger import app as bot_app
from Stranger.logger import LOGGER
from Stranger.core.razorpay import client as razorpay_client
from Stranger.utils.database.mongodatabase import Plan, Subs_Type, add_subscription, get_order_data, get_user, update_order, update_user
from Stranger.utils.helper import find_bot, get_readable_time
from config import ACCESS_TOKEN_PLAN_1, ACCESS_TOKEN_PLAN_2, DOWNLOAD_PLAN_1, DOWNLOAD_PLAN_2, PAYMENT_THUMBNAIL, RAZORPAY_WEBHOOK_SECRET
from strings import PAYMENT_HELP

webhook_app = None
webhook_server = None

# Global queue for webhook events (not just bot operations)
webhook_events_queue = queue.Queue()

def queue_webhook_event(event_type: str, entity: Dict[str, Any]):
    """
    Queue webhook events for processing in the main thread.
    This avoids event loop conflicts by moving all async operations to main thread.
    """
    try:
        event_data = {
            'event_type': event_type,
            'entity': entity,
            'timestamp': time.time()
        }
        
        webhook_events_queue.put(event_data)
        # Reduced logging - only log queuing for important events
        return True
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to queue webhook event '{event_type}': {e}")
        return False

async def process_webhook_events_queue():
    """
    Process queued webhook events in the main event loop.
    This handles both database operations and bot operations safely.
    """
    LOGGER(__name__).info("Webhook events queue processor started")
    
    while True:
        try:
            processed_count = 0
            # Process multiple events in each cycle for better efficiency
            while not webhook_events_queue.empty() and processed_count < 5:
                try:
                    event_data = webhook_events_queue.get_nowait()
                    event_type = event_data['event_type']
                    entity = event_data['entity']
                    
                    # Check if event is too old (older than 10 minutes)
                    if time.time() - event_data['timestamp'] > 600:
                        LOGGER(__name__).warning(f"Skipping old webhook event: {event_type}")
                        webhook_events_queue.task_done()
                        continue
                    
                    try:
                        if event_type == "payment_link.paid":
                            await process_successful_payment_safe(entity)
                        elif event_type == "payment_link.expired":
                            await process_expired_payment_safe(entity)
                        
                        # Reduced logging - only log successful processing
                        
                    except Exception as e:
                        LOGGER(__name__).error(f"Webhook event '{event_type}' processing failed: {e}")
                        
                    webhook_events_queue.task_done()
                    processed_count += 1
                    
                except queue.Empty:
                    break
                except Exception as e:
                    LOGGER(__name__).error(f"Error processing single webhook event: {e}")
                    break
            
            # Sleep based on whether we processed events or not
            if processed_count > 0:
                await asyncio.sleep(0.1)  # Short delay after processing
            else:
                await asyncio.sleep(0.5)  # Longer delay when queue is empty
                
        except Exception as e:
            LOGGER(__name__).error(f"Error in webhook events queue processor: {e}")
            await asyncio.sleep(1)  # Wait longer on error

def get_webhook_events_queue_status():
    """Get the current status of the webhook events queue"""
    return {
        'queue_size': webhook_events_queue.qsize(),
        'queue_empty': webhook_events_queue.empty()
    }

async def process_successful_payment_safe(entity: Dict[str, Any]):
    """Process successful payment_link.paid webhook safely in main thread"""
    try:
        await asyncio.sleep(15)

        payment_link_data = entity.get("payment_link", {}).get("entity", {})
        payment_data = entity.get("payment", {}).get("entity", {})
        
        payment_id = payment_data.get("id", "")
        amount = payment_link_data.get("amount", 0) / 100  # Convert paise to rupees
        payment_method = payment_data.get("method", "")
        
        callback_url = payment_link_data.get("callback_url", "")
        
        url_parts = callback_url.split("telegram.dog/")[1]
        username = url_parts.split("?")[0]
        start_param = callback_url.split("start=pay_")[1]
        param_parts = start_param.split("_")
        custom_order_id = param_parts[0]  # order_id
        message_id = param_parts[1]      
        
        order_details = await get_order_data(custom_order_id)
        if not order_details:
            return None
        
        await update_order(custom_order_id, "webhook_data", entity)
        
        if order_details["activated"]:
            return

        subs_type = order_details['subscription_type']
        plan = order_details['plan_type']
        user_id = order_details['user_id']
        user = await get_user(user_id)
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.datetime.now(ist)

        bot_to_send = find_bot(bot_app.managed_bots, username)

        if bot_to_send:
            bot_client:Client = bot_to_send['bot']
        else:
            bot_client = None

        if subs_type == "access_token":
            if plan == "plan1":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_1 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_1
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN1
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_1)
                await add_subscription('access', Plan.PLAN1, 'payment', user_id)
            elif plan == "plan2":
                user['is_token_verified'] = True
                user['token_expiry_time'] = time.time() + ACCESS_TOKEN_PLAN_2 if user['token_expiry_time'] <= time.time() else user['token_expiry_time'] + ACCESS_TOKEN_PLAN_2
                user['token_verify_token'] = ""
                user['token_plan'] = Plan.PLAN2
                expiry = get_readable_time(ACCESS_TOKEN_PLAN_2)
                await add_subscription('access', Plan.PLAN2, 'payment', user_id)
            user['access_token_type'] = Subs_Type.TYPE2
            if bot_client:
                try:
                    await bot_client.send_sticker(
                        chat_id=user_id,
                        sticker="CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE", 
                        disable_notification=True
                    )
                    await bot_client.send_message(
                        chat_id=user_id,
                        text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                        disable_notification=True
                    )
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to send access token messages: {e}")
        elif subs_type == "download":
            if plan == "plan1":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_1 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_1
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN1
                expiry = get_readable_time(DOWNLOAD_PLAN_1)
                await add_subscription('download',Plan.PLAN1, 'payment' ,user_id)
            elif plan == "plan2":
                user['is_download_verified'] = True
                user['download_expiry_time'] = time.time() + DOWNLOAD_PLAN_2 if user['download_expiry_time'] <= time.time() else user['download_expiry_time'] + DOWNLOAD_PLAN_2
                user['download_verify_token'] = ""
                user['download_plan'] = Plan.PLAN2
                expiry = get_readable_time(DOWNLOAD_PLAN_2)
                await add_subscription('download',Plan.PLAN2, 'payment', user_id)
            
            user['access_download_type'] = Subs_Type.TYPE2
            if bot_client:
                try:
                    await bot_client.send_sticker(
                        chat_id=user_id,
                        sticker="CAACAgUAAxkBAAENyidnruPN23VUX1tRUB_V8c0BM9sB5gACHxQAAhXfCVUQp6jhbObPejYE", 
                        disable_notification=True
                    )
                    await bot_client.send_message(
                        chat_id=user_id,
                        text=f"**• SUBSCRIPTION ACTIVATED •\n>• ACTIVATE DATE {current_time.date()}\n•SUBSCRIPTION TYPE: QR \n>• Expires In : {expiry} **",
                        disable_notification=True
                    )
                except Exception as e:
                    LOGGER(__name__).error(f"Failed to send download messages: {e}")
            
        await update_order(custom_order_id, "activated", True)
        await update_user(user_id, user)

        # Delete the payment message
        if bot_client:
            try:
                await bot_client.delete_messages(
                    chat_id=user_id,
                    message_ids=int(message_id)
                )
            except Exception as e:
                LOGGER(__name__).error(f"Failed to delete payment message: {e}")

    except Exception as e:
        LOGGER(__name__).error(f"Error processing successful payment: {e}")

async def process_expired_payment_safe(entity: Dict[str, Any]):
    """Process expired payment_link.expired webhook safely in main thread"""
    try:
        payment_link_data = entity.get("payment_link", {}).get("entity", {})
        
        amount = payment_link_data.get("amount", 0) / 100  # Convert paise to rupees
        callback_url = payment_link_data.get("callback_url", "")
        
        url_parts = callback_url.split("telegram.dog/")[1]
        username = url_parts.split("?")[0]
        start_param = callback_url.split("start=pay_")[1]
        param_parts = start_param.split("_")
        custom_order_id = param_parts[0]  # order_id
        message_id = param_parts[1]

        order_details = await get_order_data(custom_order_id)
        if not order_details:
            return None
        
        await update_order(custom_order_id, "webhook_data", entity)

        subs_type = order_details['subscription_type']
        plan = order_details['plan_type']
        user_id = order_details['user_id']
        
        bot_to_send = find_bot(bot_app.managed_bots, username)

        if bot_to_send:
            bot_client:Client = bot_to_send['bot']
        else:
            bot_client = None

        btn = [
            [
                InlineKeyboardButton(text="𝘛𝘳𝘺 𝘈𝘨𝘢𝘪𝘯", callback_data=f"payment|{subs_type}|{plan}"),
                InlineKeyboardButton(text="𝘏𝘦𝘭𝘱 𝘋𝘦𝘴𝘬", url=PAYMENT_HELP)
            ]
        ]
        if bot_client:
            try:
                await bot_client.send_video(
                    chat_id=user_id,
                    video="https://envs.sh/n1W.mp4",
                    thumb=PAYMENT_THUMBNAIL,
                    caption = ">**ITS LOOKS LIKE YOUR PAYMENT IS STILL PENDING...\n  If You're Experiencing Any Issues, You Can\n Follow The Tutorial Above Or Contact The \nHelp Desk To Get In Touch With An Admin\nFor Support.\n\n>If The ACTIVATE Button Isn't Visible After Payment, It May Be Because The Payment Was Made More Than 5 Minutes After Receiving The QR Code. The BOT Can't Provide The Button If The Payment Is Delayed.\n Send The ORDER ID (ORDERXXXX) To The \n TERABOX BOT To Activate It**",
                    reply_markup=InlineKeyboardMarkup(btn), 
                    disable_notification=True
                )
                
                await bot_client.delete_messages(
                    chat_id=user_id,
                    message_ids=int(message_id)
                )
            except Exception as e:
                LOGGER(__name__).error(f"Failed to send expired payment message: {e}")
        
    except Exception as e:
        LOGGER(__name__).error(f"Error processing expired payment: {e}")

# Keep the old functions for compatibility but make them queue events
def process_successful_payment(entity: Dict[str, Any], event: str):
    """Legacy function - now queues events for safe processing"""
    queue_webhook_event("payment_link.paid", entity)

def process_expired_payment(entity: Dict[str, Any]):
    """Legacy function - now queues events for safe processing"""
    queue_webhook_event("payment_link.expired", entity)

def verify_razorpay_signature(webhook_body: str, webhook_signature: str, webhook_secret: str) -> bool:
    """
    Verify Razorpay webhook signature using Razorpay client's utility method
    
    Args:
        webhook_body: Raw request body as string
        webhook_signature: X-Razorpay-Signature header value
        webhook_secret: Webhook secret from Razorpay dashboard
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Use Razorpay client's built-in signature verification
        # This method raises an exception if signature is invalid
        razorpay_client.utility.verify_webhook_signature(
            webhook_body,
            webhook_signature, 
            webhook_secret
        )
        return True  # If no exception is raised, signature is valid
    except Exception as e:
        LOGGER(__name__).error(f"Razorpay signature verification failed: {e}")
        return False

# Create FastAPI app
web_appp = FastAPI(
    title="Stranger Bot Webhook Server",
    description="Webhook server for handling Razorpay payment notifications",
    version="1.0.0"
)

@web_appp.get("/")
async def home_and_health():
    """Home and health check endpoint"""
    queue_status = get_webhook_events_queue_status()
    return {
        "status": "online",
        "service": "Stranger Bot Webhook Server",  
        "message": "Webhook server is running successfully!",
        "webhook_events_queue": queue_status,
        "endpoints": {
            "home": "/",
            "health": "/",
            "queue_status": "/queue/status",
            "docs": "/docs",
            "razorpay_webhook": "/webhook/razorpay/payment"
        }
    }

@web_appp.get("/queue/status")
async def queue_status():
    """Get webhook events queue status"""
    return get_webhook_events_queue_status()

@web_appp.post("/webhook/razorpay/payment")
async def razorpay_webhook_handler(request: Request):
    """Handle Razorpay payment webhooks"""
    try:
        body = await request.body()
        headers = dict(request.headers)
        
        razorpay_signature = headers.get("x-razorpay-signature")
        if not razorpay_signature:
            LOGGER(__name__).error("Missing X-Razorpay-Signature header")
            raise HTTPException(status_code=400, detail="Missing signature header")
        
        webhook_body_str = body.decode('utf-8')
        is_valid = verify_razorpay_signature(webhook_body_str, razorpay_signature, RAZORPAY_WEBHOOK_SECRET)
        if not is_valid:
            LOGGER(__name__).error("Invalid webhook signature - possible security threat!")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        try:
            payload = json.loads(webhook_body_str)
        except json.JSONDecodeError as e:
            LOGGER(__name__).error(f"Invalid JSON payload: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        event = payload.get("event", "unknown")
        entity = payload.get("payload", {})
        
        LOGGER(__name__).info(f"Webhook Event: {event}")
        
        if event == "payment_link.paid":
            process_successful_payment(entity, event)
        elif event == "payment_link.expired":
            process_expired_payment(entity)
        else:
            LOGGER(__name__).info(f"Unhandled event: {event}")
        
        # Acknowledge receipt
        return {
            "status": "success", 
            "message": "Webhook processed and queued",
            "event": event
        }
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER(__name__).error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def start_webhook_server(host='0.0.0.0', port=8080):
    """Start the webhook server using uvicorn"""
    global webhook_server
    
    try:
        LOGGER(__name__).info(f"Starting FastAPI webhook server on {host}:{port}")
        
        config = uvicorn.Config(
            app=web_appp,
            host=host,
            port=port,
            log_level="error",
            access_log=False  # Disable access logs to reduce noise
        )
        
        webhook_server = uvicorn.Server(config)
        
        await webhook_server.serve()
        
    except Exception as e:
        LOGGER(__name__).error(f"Failed to start webhook server: {e}")
        raise

async def stop_webhook_server():
    """Stop the webhook server"""
    global webhook_server
    try:
        if webhook_server:
            webhook_server.should_exit = True
            LOGGER(__name__).info("Webhook server stopped")
    except Exception as e:
        LOGGER(__name__).error(f"Error stopping webhook server: {e}")

def run_webhook_server_sync(host='0.0.0.0', port=8080):
    """Synchronous wrapper to run webhook server"""
    try:
        uvicorn.run(
            web_appp,
            host=host,
            port=port,
            log_level="error",
            access_log=False
        )
    except Exception as e:
        LOGGER(__name__).error(f"Failed to run webhook server: {e}")

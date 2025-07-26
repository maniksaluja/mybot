import time
import razorpay
from bson import ObjectId
from Stranger.utils.database.mongodatabase import create_order_data, get_order_data, update_order

client_id = "rzp_live_4Ym6UPKBUzF18c"
client_secret = "ZhZefOffkUCRAOWxnijRT5cT"

client = razorpay.Client(auth=(client_id, client_secret))


async def create_order(amount:int, user_id:int, subscription_type: str, plan_type: str, username:str, message_id:int):
    current_time = time.time()
    amount = amount *100

    order_id = f"PAYID{str(ObjectId())[-10:]}"

    callback_url =f'https://telegram.dog/{username}?start=pay_{order_id}_{message_id}'

    res = client.payment_link.create({
        "amount": amount,
        "currency": "INR",
        "description" : "Subscription",
        "customer": {
            "name": "Customer",
            "email": "xyz@example.com",
            "contact":"+919200000000"
        },
        "notify":{
            "sms":False,
            "email": False,
        },
        "upi_link": False,
        "expire_by": int(current_time + 960),
        "callback_url": callback_url,
        "callback_method": "get",
        "reminder_enable": False,
    })

    order_data = {
        'amount': amount,
        'user_id': user_id,
        'subscription_type': subscription_type,
        'plan_type': plan_type,
        "orderId": order_id,
        "payment_details": res,
        "activated": False,
        "webhook_data": {},
        "createdAt": current_time
    }

    await create_order_data(order_data)

    return {
        "created": True,
        "pay_url": res.get('short_url'),
        "order_id": order_id,
        "callback_url": callback_url
    }


async def get_payment_details(order_id:str):
    order_details = await get_order_data(order_id)


    if not order_details:
        return None

    pay_id = order_details['payment_details']['id']

    if not pay_id:
        return None

    res = client.payment_link.fetch(pay_id)

    await update_order(order_id, "payment_details", res)

    return {
        "status": res.get('status'),
        "amount" : int(res.get('amount'))/100,
        "subscription_type": order_details['subscription_type'],
        'plan_type': order_details['plan_type'],
        'user_id': order_details['user_id'],
        "pay_url": res.get('short_url'),
        "order_id": order_id,
        "callback_url": res.get('callback_url'),
        "activated": order_details["activated"]
    }
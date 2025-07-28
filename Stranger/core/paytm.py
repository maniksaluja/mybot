import time
import requests
from Stranger.utils.database.mongodatabase import get_order_data
from config import PAYMENT_HOST, PAYTM_API_KEY
from Stranger.utils.database import create_order_data, update_order_data, get_order_by_user_id, update_order
from bson import ObjectId

async def get_payment_details(query:str):
    "Returns the payment details for the given query"
    headers = {
        'x-api-key': f'{PAYTM_API_KEY}',
        'content-type':'application/json',
        'id':f'{query}',
        'type':'orderid'
    }

    result = requests.post(f"{PAYMENT_HOST}/search", headers=headers).json()

    try:
        orderList = result['orderList']
    except KeyError:
        orderList=[]
    
    data = None
    for order in orderList:
        if query == order['merchantTransId']:
            additional_info = order.get('additionalInfo', {})
            txn_amount = additional_info.get('txnAmount', {})
            
            data = {
                'orderId': order.get('merchantTransId', ''),
                'orderStatus': order.get('orderStatus', ''),
                'userPaymentAddr': additional_info.get('virtualPaymentAddr', ''),
                'customerName': additional_info.get('customerName', ''),
                'comment': additional_info.get('comment', ''),
                'amount': int(txn_amount.get('value', 0))/100,
                'paymentDate': order.get('orderCompletedTime', ''),
            }
 
    if data:
        order_details = await get_order_data(query)
        if order_details['status'] == 'SUCCESS':
            return None
        await update_order_data(query,'SUCCESS',"","",  data)

    return data

async def generate_order_id():
    random_id = str(ObjectId())[-10:]
    return f"order{random_id}"

async def create_order(amount: int, user_id: int, subscription_type: str, plan_type: str):
    """Creates a new order and saves to MongoDB"""
    MAX_RETRIES = 3
    BLOCK_TIME = 3600  # 1 hour
    
    existing_order = await get_order_by_user_id(user_id)
    current_time = time.time()
    
    if existing_order:
        time_diff = current_time - existing_order['createdAt']
        retries = existing_order.get('retries', 0)

        if existing_order['status'] == "PENDING" and time_diff < 300:
            return {
                'created': False,
                'message': 'Please Complete Your Previous Order First',
                'retry_after_seconds': int(300 - time_diff),
                'err_code':'ERR01'
            }
            
        if existing_order['status'] == "FAILED":
            if retries < MAX_RETRIES and time_diff < BLOCK_TIME:
                await update_order(existing_order['orderId'],'status', 'PENDING')
                return {
                    'created': True,
                    'qr_link': existing_order['qr_link'],
                    'pay_url': existing_order['pay_url'],
                    'order_id': existing_order['orderId'],
                }
            elif retries >= MAX_RETRIES and time_diff < BLOCK_TIME:
                return {
                    'created': False,
                    'message': 'Maximum retries reached',
                    'retry_after_seconds': int(BLOCK_TIME - time_diff),
                    'err_code':'ERR02'
                }

    order_id = await generate_order_id()
    
    header = {
        'x-api-key': PAYTM_API_KEY,
        'content-type': 'application/json',
        'order_id': order_id,
        'amount': str(amount)
    }

    try:
        res = requests.post(url=f"{PAYMENT_HOST}/create", headers=header)
        if res.status_code == 200:
            data = res.json()
            qr_link = data.get('qr', '')
            pay_url = data.get('paylink', '')

            order_data = {
                'amount': amount,
                'user_id': user_id,
                'subscription_type': subscription_type,
                'plan_type': plan_type,
                'orderId': order_id,
                'status': "PENDING",
                'qr_link': qr_link,
                'pay_url': pay_url,
                'retries': 0,
                'order_details': {},
                'createdAt': current_time
            
            }

            await create_order_data(order_data)

            return {
                'created': True,
                'pay_url': pay_url,
                'qr_link': qr_link,
                'order_id': order_id,
            }
        
        elif res.status_code == 400:
            return {
                'created': False,
                'message': 'Invalid request',
                'retry_after_seconds': 0,
                'err_code':'ERR03'
                }
        else:
            return {
                'created': False,
                'message': 'Payment gateway error',
                'retry_after_seconds': 0,
                'err_code':'ERR04'
            }
    except Exception as e:
        return {
            'created': False,
            'message': str(e),
            'retry_after_seconds': 0,
            'err_code':'ERR05'
        }

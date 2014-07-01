import logging
from datetime import datetime
from flask import json, abort
from ios.purchases import verify as verify_ios_purchase
from android.purchases import verify as verify_android_purchase
from models import Purchase
from app import app

assert not Purchase.user is NotImplementedError

def create_purchase(user, receipt, signature=None, max_reactivations=0,
                   save=False, apportable=True):
    """Add purchase to database. max_reactivations is the number
    of times a duplicated purchase can be added to the database
    (useful for restore purchases across devices). Receipt should
    be text and not parsed json. Signature is
    required for Android purchases but not used for iOS.
    Returns None if the purchase has already been activated for user,
    or max_reactivations reached or not verified. Max_reactivations
    should be used for managed/nonconsumable purchases only.
    """
    if apportable and user.platform == 'Android':
        # apportable format
        parsed = json.loads(receipt)
        signature = parsed['SKPaymentTransactionReceiptSignature']
        receipt = parsed['SKPaymentTransactionReceiptSignedData']
        logging.debug('Signature: %s' % signature)
        logging.debug('Receipt: %s' % receipt)

    if user.platform == 'Android':
        data = verify_android_purchase(receipt, signature, app.config['GOOGLE_PLAY_PUBLIC_KEY'], debug=app.config['DEBUG'])
        order_id = data['orderId']

    elif user.platform == 'iOS':
        data = verify_ios_purchase(receipt, app.config['USE_IOS_SANDBOX'])
        order_id = data['original_transaction_id']

    if Purchase.select().where((Purchase.order_id==order_id) & (Purchase.user==user)).count() > 0:
        return None

    if Purchase.select().where(Purchase.order_id==order_id).count() > max_reactivations:
        raise abort(400, 'You\'ve restored your purchase more than the max ' + \
                    'amount of times. Please contact us to request more.')

    if user.platform == 'iOS':
        purchase = Purchase(
            order_id=order_id,
            product_id=data['product_id'],
            created=datetime.fromtimestamp(int(data['original_purchase_date_ms'])/1000.0),
            purchase_token=data['transaction_id'],
            user=user,
        )
    elif user.platform == 'Android':
        purchase = Purchase(
            order_id=order_id,
            product_id=data['productId'],
            created=datetime.fromtimestamp(data['purchaseTime']/1000.0),
            purchase_token=data['purchaseToken'],
            user=user,
        )

    if save:
        purchase.save()

    return purchase

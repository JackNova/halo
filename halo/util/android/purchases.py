import logging
from datetime import datetime, timedelta
from flask import current_app, json, abort
import base64
from Crypto.Hash import SHA # requires PyCrypto
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from models import User, Purchase
from peewee import fn

# set max number of days from original purchase time to our server receiving
# the purchase order in order to minimize piracy
# NOTE: android.test.purchased purchaseTime is 1970-01-01 (eg 0 in epoch time)
# NOTE: a purchase can be restored on another device many days after it was originally purchased
#MAX_DAYS_DELTA = 7

"""
Sample purchase data (parsed signed_data):
{
  "nonce": 8216863948870587915,
  "orders": [
    {
      "notificationId": "5711431302225752535",
      "orderId": "12999763169054705758.1360379356271522",
      "packageName": "com.apportable.spinpushtest",
      "productId": "com.apportable.spin.consumable1",
      "purchaseTime":1376417210000,
      "purchaseState": 0,
      "developerPayload": "NtWo0uMJvKa3ODzITNfEGDVqtrb8iPnV0Z5iWj17",
      "purchaseToken": "wksvobhogeooxapwhpyxpuly"
    }
  ]
}

Sample purchase data (iabv3)
{
    "packageName": "me.likesplus",
    "orderId": "transactionId.android.test.purchased",
    "productId": "android.test.purchased",
    "developerPayload": "3VV8JQ9KpE2j5ShtuCUaM800QEde8dxyGSpM5gZe",
    "purchaseTime": 0,
    "purchaseState": 0,
    "purchaseToken": "inapp:me.likesplus:android.test.purchased"
}
"""

def verify(signed_data, signature_base64, public_key, iabv3=True, debug=False):
    """Returns whether the given data was signed with the private key.
    """
    h = SHA.new()
    h.update(signed_data)

    # the key from Google Play is a X.509 subjectPublicKeyInfo DER SEQUENCE
    public_key = RSA.importKey(base64.standard_b64decode(public_key))
    # Scheme is RSASSA-PKCS1-v1_5.
    verifier = PKCS1_v1_5.new(public_key)
    # The signature is base64 encoded.
    signature = base64.standard_b64decode(signature_base64)

    if debug:
        order = json.loads(signed_data)
        if not iabv3:
            order = order['orders'][0]
        if order['productId'] == 'android.test.purchased':
            # test purchases don't have purchase token
            order['purchaseToken'] = 'android.test.purchased'
            return order

    assert verifier.verify(h, signature)

    data = json.loads(signed_data)
    if not iabv3:
        data = data['orders'][0]
    return data

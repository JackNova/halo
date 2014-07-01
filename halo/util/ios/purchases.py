import logging
import urllib2, base64, json

"""
Sample response from app verification url:
{
  'status': 21006,
  'receipt': {
    'purchase_date_pst': '2012-03-16 15:33:58 America/Los_Angeles',
    'expires_date': '1331937538000',
    'product_id': 'your_product_id',
    'original_transaction_id': '1222000034404994',
    'expires_date_formatted_pst': '2012-03-16 15:38:58 America/Los_Angeles',
    'original_purchase_date_pst': '2012-03-16 15:33:59 America/Los_Angeles',
    'item_id': 'your_item_id',
    'original_purchase_date': '2012-03-16 22:33:59 Etc/GMT',
    'expires_date_formatted': '2012-03-16 22:38:58 Etc/GMT',
    'bvrs': 'your_version',
    'original_purchase_date_ms': '1331937239000',
    'hosted_iap_version': '2.718',
    'purchase_date': '2012-03-16 22:33:58 Etc/GMT',
    'web_order_line_item_id': 'your_id',
    'purchase_date_ms': '1331937238000',
    'bid': 'your_bid',
    'transaction_id': '1222000034419520',
    'quantity': '1'
  }
}

Possible status codes:
0: Success
21000: The App Store could not read the JSON object you provided.
21002: The data in the receipt-data property was malformed or missing.
21003: The receipt could not be authenticated.
21004: The shared secret you provided does not match the shared secret on file for your account.
Only returned for iOS 6 style transaction receipts for auto-renewable subscriptions.
21005: The receipt server is not currently available.
21006: This receipt is valid but the subscription has expired. When this status code is returned to your server, the receipt data is also decoded and returned as part of the response.
Only returned for iOS 6 style transaction receipts for auto-renewable subscriptions.
21007: This receipt is from the test environment, but it was sent to the production environment for verification. Send it to the test environment instead.
21008: This receipt is from the production environment, but it was sent to the test environment for verification. Send it to the production environment instead.

"""

def verify(receipt, sandbox=False, sandbox_fallback=True):
    if sandbox:
        url = 'https://sandbox.itunes.apple.com/verifyReceipt'
    else:
        url = 'https://buy.itunes.apple.com/verifyReceipt'

    encoded_receipt = base64.b64encode(receipt)
    data = json.dumps({'receipt-data': encoded_receipt})

    response = urllib2.urlopen(url, data)
    result = json.loads(response.read())
    response.close()

    # retry if receipt for wrong server (apple review process uses sandbox)
    if result['status'] in [21008, 21007] and sandbox_fallback:
        logging.debug('Error with status %s. Retrying with sandbox %s' % (result['status'], not sandbox))
        return verify(receipt, not sandbox, False)

    if not result['status'] == 0:
        raise ValueError('Receipt invalid: %s' % result['status'])
    return result['receipt']

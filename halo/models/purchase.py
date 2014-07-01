import logging
from peewee import *
from datetime import datetime
from app import db

class BasePurchase(db.Model):
    """A purchase such as an in app purchase/subscription, or
    stripe purchase/subscription
    """
    # the number of duplicate subscription_order_id allowed
    # this is used to prevent piracy but also allow user to restore
    # purchases on multiple devices (valid only for Android purchases)
    #MAX_DUPLICATE_ORDER_ID = 5

    user = NotImplementedError
    # example:
    # user = ForeignKeyField(User, related_name='purchases')

    # a name given to the product purchased to identify it
    # TODO: just get rid of this?
    #name = CharField(index=True)

    # the android or ios product id
    product_id = CharField(null=True)

    # TODO: mark as android or stripe, etc...
    # the type of purchase subs for subscription and inapp for purchase
    #type = CharField(choices=[
    #    ('inapp', 'In-App Purchase'),
    #    ('subs', 'Subscription'),
    #])

    # TODO: platform and user

    # the stripe customer id, or the purchaseToken on Android
    purchase_token = CharField()

    # on Android the orderId should be checked to make sure it is unique
    # might be able to get rid of this and just use subscription_id value instead
    order_id = CharField(null=True, index=True)

    # used to calculate expiration of subscription so we can check if it's been
    # renewed (must be manually set with value from purchase provider eg. stripe)
    created = DateTimeField(null=True)

    # the expiration date (valid only for subscriptions)
    #expiration = DateTimeField(null=True, index=True)
